import { spawn, type ChildProcess } from "node:child_process";
import { EventEmitter } from "node:events";
import {
  createInterface,
  type Interface as ReadlineInterface,
} from "node:readline";
import type { JsonRpcRequest, JsonRpcResponse } from "../types/protocol.js";
import type {
  ClientStatus,
  NotificationHandler,
  PendingRequest,
  SageClientOptions,
} from "./types.js";

const DEFAULT_OPTIONS: Required<SageClientOptions> = {
  command: "sage",
  args: ["serve"],
  agentConfig: "",
  requestTimeout: 30_000,
  reconnectRetries: 3,
};

export class SageClient extends EventEmitter {
  private process: ChildProcess | null = null;
  private readline: ReadlineInterface | null = null;
  private nextId = 1;
  private pending = new Map<number | string, PendingRequest>();
  private notificationHandlers = new Map<string, Set<NotificationHandler>>();
  private options: Required<SageClientOptions>;
  private _status: ClientStatus = "disconnected";
  private reconnectAttempts = 0;
  private isDisposed = false;

  constructor(options?: SageClientOptions) {
    super();
    this.options = {
      command: options?.command ?? DEFAULT_OPTIONS.command,
      args: options?.args ?? DEFAULT_OPTIONS.args,
      agentConfig: options?.agentConfig ?? DEFAULT_OPTIONS.agentConfig,
      requestTimeout: options?.requestTimeout ?? DEFAULT_OPTIONS.requestTimeout,
      reconnectRetries: options?.reconnectRetries ?? DEFAULT_OPTIONS.reconnectRetries,
    };
  }

  get status(): ClientStatus {
    return this._status;
  }

  async spawn(): Promise<void> {
    if (this._status === "connected" || this._status === "connecting") {
      return;
    }

    this.isDisposed = false;
    this.setStatus("connecting");

    const args = [...this.options.args];
    if (this.options.agentConfig) {
      args.push("--agent-config", this.options.agentConfig);
    }

    try {
      // Backend process isolates tool subprocess stdin from this JSON-RPC pipe,
      // so protocol traffic on stdin/stdout is not contended by spawned tools.
      const child = spawn(this.options.command, args, {
        stdio: ["pipe", "pipe", "pipe"],
      });

      if (!child.stdin || !child.stdout) {
        throw new Error("Failed to create sage subprocess stdio streams");
      }

      this.process = child;

      // Consume stderr to prevent it from buffering and flushing to the
      // parent terminal, which would corrupt Ink's rendering output.
      child.stderr?.resume();

      this.readline = createInterface({
        input: child.stdout,
        crlfDelay: Infinity,
      });
      this.readline.on("line", (line) => this.handleLine(line));

      child.on("error", (error) => {
        this.setStatus("error");
        this.emit("error", error);
      });

      child.on("close", () => {
        this.cleanupProcessHandles();
        this.rejectAllPending(new Error("Sage subprocess closed"));

        if (!this.isDisposed) {
          this.setStatus("disconnected");
          this.emit("disconnected");
          void this.tryReconnect();
        }
      });

      await this.request("initialize", {});
      this.reconnectAttempts = 0;
      this.setStatus("connected");
      this.emit("connected");
    } catch (error) {
      this.cleanupProcessHandles();
      this.rejectAllPending(new Error("Failed to start sage client"));
      this.setStatus("error");
      throw error;
    }
  }

  async request<T = unknown>(
    method: string,
    params?: Record<string, unknown>,
  ): Promise<T> {
    if (!this.process?.stdin || this.process.stdin.destroyed) {
      throw new Error("Sage client is not connected");
    }

    const id = this.nextId++;
    const request: JsonRpcRequest = {
      jsonrpc: "2.0",
      id,
      method,
      ...(params ? { params } : {}),
    };

    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Request timed out: ${method}`));
      }, this.options.requestTimeout);

      this.pending.set(id, {
        resolve: (result) => resolve(result as T),
        reject,
        timer,
      });

      try {
        this.write(request);
      } catch (error) {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(
          error instanceof Error
            ? error
            : new Error("Failed to write request"),
        );
      }
    });
  }

  onNotification(method: string, callback: NotificationHandler): () => void {
    const current = this.notificationHandlers.get(method) ?? new Set();
    current.add(callback);
    this.notificationHandlers.set(method, current);

    return () => {
      const handlers = this.notificationHandlers.get(method);
      if (!handlers) {
        return;
      }

      handlers.delete(callback);
      if (handlers.size === 0) {
        this.notificationHandlers.delete(method);
      }
    };
  }

  dispose(): void {
    this.isDisposed = true;

    this.cleanupProcessHandles();
    this.rejectAllPending(new Error("Sage client disposed"));
    this.notificationHandlers.clear();

    this.setStatus("disconnected");
    this.emit("disconnected");
  }

  private handleLine(line: string): void {
    if (!line.trim()) {
      return;
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(line);
    } catch {
      return;
    }

    if (!this.isRecord(parsed)) {
      return;
    }

    if ("id" in parsed) {
      const response = parsed as unknown as JsonRpcResponse;
      const pending = this.pending.get(response.id);
      if (!pending) {
        return;
      }

      clearTimeout(pending.timer);
      this.pending.delete(response.id);

      if (response.error) {
        pending.reject(new Error(response.error.message));
        return;
      }

      pending.resolve(response.result);
      return;
    }

    if ("method" in parsed && typeof parsed.method === "string") {
      const handlers = this.notificationHandlers.get(parsed.method);
      if (!handlers || handlers.size === 0) {
        return;
      }

      const params = this.isRecord(parsed.params) ? parsed.params : {};
      for (const handler of handlers) {
        try {
          handler(params);
        } catch (error) {
          this.emit(
            "error",
            error instanceof Error
              ? error
              : new Error("Notification handler failed"),
          );
        }
      }
    }
  }

  private write(data: object): void {
    if (!this.process?.stdin || this.process.stdin.destroyed) {
      throw new Error("Sage client stdin is not available");
    }

    const payload = `${JSON.stringify(data)}\n`;
    this.process.stdin.write(payload, (error) => {
      if (error) {
        this.emit("error", new Error(`Failed to write to sage process: ${error.message}`));
      }
    });
  }

  private rejectAllPending(error: Error): void {
    for (const [id, pending] of this.pending) {
      clearTimeout(pending.timer);
      pending.reject(error);
      this.pending.delete(id);
    }
  }

  private cleanupProcessHandles(): void {
    this.readline?.close();
    this.readline = null;

    if (this.process?.kill) {
      this.process.kill();
    }
    this.process = null;
  }

  private async tryReconnect(): Promise<void> {
    if (this.isDisposed || this.options.reconnectRetries <= 0) {
      return;
    }

    while (
      this.reconnectAttempts < this.options.reconnectRetries &&
      !this.isDisposed &&
      this._status === "disconnected"
    ) {
      this.reconnectAttempts += 1;
      try {
        await this.spawn();
        return;
      } catch (error) {
        if (this.reconnectAttempts >= this.options.reconnectRetries) {
          this.setStatus("error");
          this.emit(
            "error",
            error instanceof Error
              ? error
              : new Error("Failed to reconnect sage process"),
          );
          return;
        }

        await new Promise((resolve) => setTimeout(resolve, 300));
      }
    }
  }

  private setStatus(status: ClientStatus): void {
    this._status = status;
  }

  private isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null;
  }
}

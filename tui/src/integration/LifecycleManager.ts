import { spawn, type ChildProcess } from "node:child_process";
import {
  createInterface,
  type Interface as ReadlineInterface,
} from "node:readline";

interface JsonRpcResponse {
  id: number;
  result?: unknown;
  error?: { message?: string };
}

interface LifecycleOptions {
  command: string;
  args: string[];
  onCrash?: (exitCode: number) => void;
  onConnected?: () => void;
  heartbeatIntervalMs?: number;
  heartbeatTimeoutMs?: number;
  shutdownWaitMs?: number;
  terminateWaitMs?: number;
}

interface PendingRequest {
  resolve: (value: unknown) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

const HEARTBEAT_INTERVAL_MS = 10_000;
const HEARTBEAT_TIMEOUT_MS = 2_000;
const SHUTDOWN_WAIT_MS = 2_000;
const TERMINATE_WAIT_MS = 1_000;

export class LifecycleManager {
  private readonly command: string;
  private readonly args: string[];
  private readonly heartbeatIntervalMs: number;
  private readonly heartbeatTimeoutMs: number;
  private readonly shutdownWaitMs: number;
  private readonly terminateWaitMs: number;

  private process: ChildProcess | null = null;
  private readline: ReadlineInterface | null = null;
  private nextId = 1;
  private pending = new Map<number, PendingRequest>();
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private consecutiveHeartbeatFailures = 0;
  private crashHandlers = new Set<(exitCode: number) => void>();

  private _isConnected = false;
  private _crashCount = 0;
  private isShuttingDown = false;

  constructor(options: LifecycleOptions) {
    this.command = options.command;
    this.args = options.args;
    this.heartbeatIntervalMs =
      options.heartbeatIntervalMs ?? HEARTBEAT_INTERVAL_MS;
    this.heartbeatTimeoutMs = options.heartbeatTimeoutMs ?? HEARTBEAT_TIMEOUT_MS;
    this.shutdownWaitMs = options.shutdownWaitMs ?? SHUTDOWN_WAIT_MS;
    this.terminateWaitMs = options.terminateWaitMs ?? TERMINATE_WAIT_MS;

    if (options.onCrash) {
      this.crashHandlers.add(options.onCrash);
    }
    if (options.onConnected) {
      this.onConnected = options.onConnected;
    }
  }

  get isConnected(): boolean {
    return this._isConnected;
  }

  get crashCount(): number {
    return this._crashCount;
  }

  onConnected: (() => void) | null = null;

  onCrash(callback: (exitCode: number) => void): void {
    this.crashHandlers.add(callback);
  }

  getProcess(): ChildProcess | null {
    return this.process;
  }

  async startup(): Promise<void> {
    if (this.process && this._isConnected) {
      return;
    }

    this.isShuttingDown = false;
    const child = spawn(this.command, this.args, {
      stdio: ["pipe", "pipe", "pipe"],
    });

    if (!child.stdin || !child.stdout) {
      throw new Error("Failed to create subprocess stdio streams");
    }

    this.process = child;
    this.readline = createInterface({
      input: child.stdout,
      crlfDelay: Infinity,
    });
    this.readline.on("line", this.handleLine);

    child.on("exit", this.handleExit);
    child.on("error", this.handleError);

    await this.sendRequest("initialize", {}, this.heartbeatTimeoutMs);
    this._isConnected = true;
    this.consecutiveHeartbeatFailures = 0;
    this.startHeartbeat();
    this.onConnected?.();
  }

  async shutdown(): Promise<void> {
    this.isShuttingDown = true;
    this.stopHeartbeat();

    if (this.process?.stdin && !this.process.stdin.destroyed) {
      try {
        await this.sendRequest("shutdown", {}, this.heartbeatTimeoutMs);
      } catch { /* best-effort: ignore if already shutting down */ }
    }

    await this.delay(this.shutdownWaitMs);
    this.process?.kill("SIGTERM");

    await this.delay(this.terminateWaitMs);
    if (this.process && !this.process.killed) {
      this.process.kill("SIGKILL");
    }

    this.disposeHandles();
    this._isConnected = false;
    this.isShuttingDown = false;
  }

  async restart(): Promise<void> {
    this._crashCount += 1;

    if (this.process) {
      await this.shutdown();
    }

    await this.startup();
  }

  private readonly handleLine = (line: string): void => {
    if (!line.trim()) {
      return;
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(line);
    } catch {
      return;
    }

    if (!this.isRecord(parsed) || typeof parsed.id !== "number") {
      return;
    }

    const response: JsonRpcResponse = {
      id: parsed.id,
      ...("result" in parsed ? { result: parsed.result } : {}),
      ...(this.hasError(parsed) ? { error: parsed.error } : {}),
    };
    const pending = this.pending.get(response.id);
    if (!pending) {
      return;
    }

    clearTimeout(pending.timer);
    this.pending.delete(response.id);

    if (response.error?.message) {
      pending.reject(new Error(response.error.message));
      return;
    }

    pending.resolve(response.result);
  };

  private readonly handleExit = (exitCode: number | null): void => {
    const code = exitCode ?? -1;
    this._isConnected = false;
    this.stopHeartbeat();
    this.rejectPending(new Error("Lifecycle process exited"));
    this.disposeHandles();

    if (!this.isShuttingDown) {
      this.emitCrash(code);
    }
  };

  private readonly handleError = (): void => {
    this._isConnected = false;
  };

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      void this.sendRequest("ping", {}, this.heartbeatTimeoutMs)
        .then(() => {
          this.consecutiveHeartbeatFailures = 0;
        })
        .catch(() => {
          this.consecutiveHeartbeatFailures += 1;
          if (this.consecutiveHeartbeatFailures >= 3) {
            this._isConnected = false;
            this.stopHeartbeat();
            this.emitCrash(-1);
          }
        });
    }, this.heartbeatIntervalMs);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private sendRequest(
    method: string,
    params: Record<string, unknown>,
    timeoutMs: number,
  ): Promise<unknown> {
    if (!this.process?.stdin || this.process.stdin.destroyed) {
      return Promise.reject(new Error("Lifecycle process is not connected"));
    }

    const id = this.nextId++;
    const payload = {
      jsonrpc: "2.0",
      id,
      method,
      params,
    };

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Request timed out: ${method}`));
      }, timeoutMs);

      this.pending.set(id, { resolve, reject, timer });

      this.process?.stdin?.write(`${JSON.stringify(payload)}\n`, (error) => {
        if (error) {
          clearTimeout(timer);
          this.pending.delete(id);
          reject(error);
        }
      });
    });
  }

  private rejectPending(error: Error): void {
    for (const [id, pending] of this.pending) {
      clearTimeout(pending.timer);
      pending.reject(error);
      this.pending.delete(id);
    }
  }

  private disposeHandles(): void {
    if (this.readline) {
      this.readline.off("line", this.handleLine);
      this.readline.close();
      this.readline = null;
    }

    if (this.process) {
      this.process.off("exit", this.handleExit);
      this.process.off("error", this.handleError);
    }

    this.process = null;
  }

  private emitCrash(exitCode: number): void {
    for (const callback of this.crashHandlers) {
      callback(exitCode);
    }
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => {
      setTimeout(resolve, ms);
    });
  }

  private isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null;
  }

  private hasError(
    value: Record<string, unknown>,
  ): value is Record<string, unknown> & { error: { message?: string } } {
    if (!("error" in value)) {
      return false;
    }

    const error = value.error;
    return typeof error === "object" && error !== null;
  }
}

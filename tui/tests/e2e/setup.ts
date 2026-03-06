import { spawn, spawnSync, type ChildProcessWithoutNullStreams } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createInterface, type Interface } from "node:readline";
import { afterAll, afterEach } from "vitest";

type JsonRpcId = number | string;

interface JsonRpcRequest {
  jsonrpc: "2.0";
  method: string;
  id?: JsonRpcId;
  params?: Record<string, unknown>;
}

interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: JsonRpcId;
  result?: unknown;
  error?: {
    code: number;
    message: string;
  };
}

interface JsonRpcNotification {
  jsonrpc: "2.0";
  method: string;
  params?: Record<string, unknown>;
}

class JsonRpcRequestError extends Error {
  constructor(
    public readonly code: number,
    message: string,
  ) {
    super(message);
    this.name = "JsonRpcRequestError";
  }
}

interface PendingRequest {
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
  timeout: NodeJS.Timeout;
}

interface NotificationWaiter {
  resolve: (value: Record<string, unknown>) => void;
  reject: (reason: unknown) => void;
  timeout: NodeJS.Timeout;
}

export interface SageTestClientOptions {
  agentConfigPath?: string;
  command?: string;
  requestTimeoutMs?: number;
}

interface ServeCommand {
  command: string;
  prefixArgs: string[];
}

const here = fileURLToPath(new URL(".", import.meta.url));
const defaultAgentPath = resolve(here, "test-agent.md");
const activeClients = new Set<SageTestClient>();
let cleanupHooksInstalled = false;

export class SageTestClient {
  private readonly process: ChildProcessWithoutNullStreams;
  private readonly lines: Interface;
  private readonly pendingRequests = new Map<JsonRpcId, PendingRequest>();
  private readonly notificationQueues = new Map<string, Record<string, unknown>[]>();
  private readonly notificationWaiters = new Map<string, NotificationWaiter[]>();
  private readonly requestTimeoutMs: number;
  private nextRequestId = 1;
  private closed = false;
  private readonly stderrChunks: string[] = [];

  constructor(options: SageTestClientOptions = {}) {
    const serveCommand = resolveServeCommand(options.command);
    const agentConfigPath = options.agentConfigPath ?? defaultAgentPath;
    this.requestTimeoutMs = options.requestTimeoutMs ?? 10000;

    this.process = spawn(
      serveCommand.command,
      [...serveCommand.prefixArgs, "serve", "--agent-config", agentConfigPath],
      {
        stdio: ["pipe", "pipe", "pipe"],
      },
    );
    this.lines = createInterface({ input: this.process.stdout });

    this.process.stderr.on("data", (chunk: Buffer | string) => {
      this.stderrChunks.push(chunk.toString());
    });

    this.process.on("error", (error) => {
      this.rejectAllPending(`sage serve failed to start: ${error.message}`);
    });

    this.process.once("exit", (code, signal) => {
      if (!this.closed) {
        this.rejectAllPending(
          `sage serve exited before request completed (code=${String(code)}, signal=${String(signal)})`,
        );
      }
      this.closed = true;
      this.lines.close();
    });

    this.lines.on("line", (line) => {
      this.handleLine(line);
    });
  }

  get pid(): number {
    return this.process.pid ?? -1;
  }

  get stderrOutput(): string {
    return this.stderrChunks.join("");
  }

  async request(
    method: string,
    params: Record<string, unknown> = {},
    id?: JsonRpcId,
  ): Promise<unknown> {
    const requestId = id ?? this.nextRequestId;
    if (id === undefined) {
      this.nextRequestId += 1;
    }

    const payload: JsonRpcRequest = {
      jsonrpc: "2.0",
      method,
      id: requestId,
      params,
    };

    const promise = new Promise<unknown>((resolvePromise, rejectPromise) => {
      const timeout = setTimeout(() => {
        this.pendingRequests.delete(requestId);
        rejectPromise(new Error(`Timed out waiting for response to ${method}`));
      }, this.requestTimeoutMs);

      this.pendingRequests.set(requestId, {
        resolve: resolvePromise,
        reject: rejectPromise,
        timeout,
      });
    });

    this.writeLine(payload);
    return promise;
  }

  sendRaw(line: string): void {
    if (this.closed) {
      throw new Error("Cannot write to closed sage serve process");
    }
    this.process.stdin.write(`${line}\n`);
  }

  requestRaw(
    line: string,
    id: JsonRpcId,
    timeoutMs: number = this.requestTimeoutMs,
  ): Promise<unknown> {
    const promise = new Promise<unknown>((resolvePromise, rejectPromise) => {
      const timeout = setTimeout(() => {
        this.pendingRequests.delete(id);
        rejectPromise(new Error(`Timed out waiting for response to raw request id=${String(id)}`));
      }, timeoutMs);

      this.pendingRequests.set(id, {
        resolve: resolvePromise,
        reject: rejectPromise,
        timeout,
      });
    });

    this.sendRaw(line);
    return promise;
  }

  async waitForNotification(
    method: string,
    timeoutMs: number = this.requestTimeoutMs,
  ): Promise<Record<string, unknown>> {
    const queue = this.notificationQueues.get(method);
    if (queue && queue.length > 0) {
      const next = queue.shift();
      if (next !== undefined) {
        return next;
      }
    }

    return new Promise<Record<string, unknown>>((resolvePromise, rejectPromise) => {
      const timeout = setTimeout(() => {
        const waiters = this.notificationWaiters.get(method) ?? [];
        this.notificationWaiters.set(
          method,
          waiters.filter((waiter) => waiter.timeout !== timeout),
        );
        rejectPromise(new Error(`Timed out waiting for notification: ${method}`));
      }, timeoutMs);

      const waiters = this.notificationWaiters.get(method) ?? [];
      waiters.push({ resolve: resolvePromise, reject: rejectPromise, timeout });
      this.notificationWaiters.set(method, waiters);
    });
  }

  async collectNotifications(
    method: string,
    count: number,
    timeoutMs: number = this.requestTimeoutMs,
  ): Promise<Record<string, unknown>[]> {
    const results: Record<string, unknown>[] = [];
    while (results.length < count) {
      const remaining = count - results.length;
      const budget = Math.max(500, timeoutMs / Math.max(remaining, 1));
      const next = await this.waitForNotification(method, budget);
      results.push(next);
    }
    return results;
  }

  async close(): Promise<void> {
    if (this.closed) {
      return;
    }

    this.closed = true;
    this.lines.close();

    const pid = this.process.pid;
    if (pid === undefined) {
      this.rejectAllPending("sage serve process had no pid");
      return;
    }

    this.process.kill("SIGTERM");
    const exitedGracefully = await this.waitForExit(2000);
    if (!exitedGracefully) {
      this.process.kill("SIGKILL");
      await this.waitForExit(2000);
    }

    this.rejectAllPending("Sage test client closed");
  }

  private waitForExit(timeoutMs: number): Promise<boolean> {
    if (this.process.exitCode !== null || this.process.signalCode !== null) {
      return Promise.resolve(true);
    }

    return new Promise<boolean>((resolvePromise) => {
      const timeout = setTimeout(() => {
        cleanup();
        resolvePromise(false);
      }, timeoutMs);

      const onExit = () => {
        cleanup();
        resolvePromise(true);
      };

      const cleanup = () => {
        clearTimeout(timeout);
        this.process.off("exit", onExit);
      };

      this.process.once("exit", onExit);
    });
  }

  private writeLine(payload: JsonRpcRequest): void {
    if (this.closed) {
      throw new Error("Cannot send request to closed sage serve process");
    }

    this.process.stdin.write(`${JSON.stringify(payload)}\n`);
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

    if (typeof parsed !== "object" || parsed === null) {
      return;
    }

    const message = parsed as Partial<JsonRpcResponse & JsonRpcNotification>;
    if (typeof message.id === "number" || typeof message.id === "string") {
      this.handleResponse(message as JsonRpcResponse);
      return;
    }

    if (typeof message.method === "string") {
      this.handleNotification(message as JsonRpcNotification);
    }
  }

  private handleResponse(message: JsonRpcResponse): void {
    const pending = this.pendingRequests.get(message.id);
    if (!pending) {
      return;
    }
    this.pendingRequests.delete(message.id);
    clearTimeout(pending.timeout);

    if (message.error) {
      pending.reject(new JsonRpcRequestError(message.error.code, message.error.message));
      return;
    }

    pending.resolve(message.result);
  }

  private handleNotification(message: JsonRpcNotification): void {
    const method = message.method;
    const params = message.params ?? {};
    const waiters = this.notificationWaiters.get(method);

    if (waiters && waiters.length > 0) {
      const waiter = waiters.shift();
      if (waiter) {
        clearTimeout(waiter.timeout);
        waiter.resolve(params);
      }
      this.notificationWaiters.set(method, waiters);
      return;
    }

    const queue = this.notificationQueues.get(method) ?? [];
    queue.push(params);
    this.notificationQueues.set(method, queue);
  }

  private rejectAllPending(reason: string): void {
    for (const [, pending] of this.pendingRequests) {
      clearTimeout(pending.timeout);
      pending.reject(new Error(reason));
    }
    this.pendingRequests.clear();

    for (const [, waiters] of this.notificationWaiters) {
      for (const waiter of waiters) {
        clearTimeout(waiter.timeout);
        waiter.reject(new Error(reason));
      }
    }
    this.notificationWaiters.clear();
  }
}

function resolveServeCommand(explicitCommand?: string): ServeCommand {
  if (explicitCommand) {
    return { command: explicitCommand, prefixArgs: [] };
  }

  const direct = spawnSync("sage", ["--help"], { encoding: "utf8" });
  const helpText = `${direct.stdout ?? ""}${direct.stderr ?? ""}`;
  if (direct.status === 0 && helpText.includes("serve")) {
    return { command: "sage", prefixArgs: [] };
  }

  return { command: "uv", prefixArgs: ["run", "sage"] };
}

export function createClient(options: SageTestClientOptions = {}): SageTestClient {
  const client = new SageTestClient(options);
  activeClients.add(client);
  return client;
}

export function getDefaultAgentPath(): string {
  return defaultAgentPath;
}

export function installE2ECleanupHooks(): void {
  if (cleanupHooksInstalled) {
    return;
  }

  cleanupHooksInstalled = true;

  const closeActiveClients = async (): Promise<void> => {
    const clients = Array.from(activeClients);
    activeClients.clear();
    await Promise.all(clients.map((client) => client.close()));
  };

  afterEach(async () => {
    await closeActiveClients();
  });

  afterAll(async () => {
    await closeActiveClients();
  });
}

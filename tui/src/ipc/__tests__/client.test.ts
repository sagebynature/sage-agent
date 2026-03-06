import { EventEmitter } from "node:events";
import { PassThrough } from "node:stream";
import { spawn } from "node:child_process";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SageClient } from "../client.js";

vi.mock("node:child_process", () => ({
  spawn: vi.fn(),
}));

type SpawnResult = ReturnType<typeof spawn>;

interface MockProcess extends EventEmitter {
  stdin: PassThrough;
  stdout: PassThrough;
  stderr: PassThrough;
  kill: () => boolean;
  pid: number;
}

const createMockProcess = (): MockProcess => {
  const proc = Object.assign(new EventEmitter(), {
    stdin: new PassThrough(),
    stdout: new PassThrough(),
    stderr: new PassThrough(),
    kill: vi.fn(() => true),
    pid: 12345,
  });

  return proc;
};

const readNextRequest = async (proc: MockProcess): Promise<Record<string, unknown>> => {
  const chunk = await new Promise<string>((resolve) => {
    proc.stdin.once("data", (data: Buffer) => resolve(data.toString("utf8")));
  });

  const line = chunk.split("\n").find((entry) => entry.trim().length > 0) ?? "";
  return JSON.parse(line) as Record<string, unknown>;
};

const emitServerLine = async (proc: MockProcess, payload: object): Promise<void> => {
  proc.stdout.write(`${JSON.stringify(payload)}\n`);
  await new Promise((resolve) => setTimeout(resolve, 0));
};

const connectClient = async (
  client: SageClient,
  proc: MockProcess,
): Promise<void> => {
  const spawnPromise = client.spawn();
  const initRequest = await readNextRequest(proc);

  await emitServerLine(proc, {
    jsonrpc: "2.0",
    id: initRequest.id,
    result: { ok: true },
  });

  await spawnPromise;
};

describe("SageClient", () => {
  const mockSpawn = vi.mocked(spawn);
  let proc: MockProcess;

  beforeEach(() => {
    proc = createMockProcess();
    mockSpawn.mockReturnValue(proc as unknown as SpawnResult);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("uses default command and args", async () => {
    const client = new SageClient();

    const spawnPromise = client.spawn();
    const initRequest = await readNextRequest(proc);
    await emitServerLine(proc, {
      jsonrpc: "2.0",
      id: initRequest.id,
      result: { ok: true },
    });
    await spawnPromise;

    expect(mockSpawn).toHaveBeenCalledWith("sage", ["serve"], {
      stdio: ["pipe", "pipe", "pipe"],
    });
    expect(client.status).toBe("connected");
  });

  it("uses custom command, args, and agent config", async () => {
    const client = new SageClient({
      command: "custom-sage",
      args: ["serve", "--debug"],
      agentConfig: "./AGENTS.md",
    });

    const spawnPromise = client.spawn();
    const initRequest = await readNextRequest(proc);
    await emitServerLine(proc, {
      jsonrpc: "2.0",
      id: initRequest.id,
      result: { ok: true },
    });
    await spawnPromise;

    expect(mockSpawn).toHaveBeenCalledWith(
      "custom-sage",
      ["serve", "--debug", "--agent-config", "./AGENTS.md"],
      { stdio: ["pipe", "pipe", "pipe"] },
    );
  });

  it("request sends JSON-RPC payload", async () => {
    const client = new SageClient();
    await connectClient(client, proc);

    const responsePromise = client.request("session/list", { agentName: "assistant" });
    const request = await readNextRequest(proc);

    expect(request.jsonrpc).toBe("2.0");
    expect(request.id).toBeTypeOf("number");
    expect(request.method).toBe("session/list");
    expect(request.params).toEqual({ agentName: "assistant" });

    await emitServerLine(proc, {
      jsonrpc: "2.0",
      id: request.id,
      result: { sessions: [] },
    });

    await expect(responsePromise).resolves.toEqual({ sessions: [] });
  });

  it("request resolves when matching response is received", async () => {
    const client = new SageClient();
    await connectClient(client, proc);

    const promise = client.request<{ status: string }>("agent/run", {
      message: "hello",
    });
    const request = await readNextRequest(proc);

    await emitServerLine(proc, {
      jsonrpc: "2.0",
      id: request.id,
      result: { status: "started" },
    });

    await expect(promise).resolves.toEqual({ status: "started" });
  });

  it("request rejects on timeout", async () => {
    const client = new SageClient({ requestTimeout: 10 });
    await connectClient(client, proc);

    vi.useFakeTimers();

    const promise = client.request("agent/run", { message: "timeout" });
    const rejection = expect(promise).rejects.toThrow(
      "Request timed out: agent/run",
    );
    await readNextRequest(proc);

    await vi.advanceTimersByTimeAsync(20);
    await rejection;
  });

  it("notification handler is called for matching method", async () => {
    const client = new SageClient();
    await connectClient(client, proc);

    const handler = vi.fn();
    client.onNotification("stream/delta", handler);

    await emitServerLine(proc, {
      jsonrpc: "2.0",
      method: "stream/delta",
      params: { delta: "hello" },
    });

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith({ delta: "hello" });
  });

  it("notification handler is not called for non-matching method", async () => {
    const client = new SageClient();
    await connectClient(client, proc);

    const handler = vi.fn();
    client.onNotification("stream/delta", handler);

    await emitServerLine(proc, {
      jsonrpc: "2.0",
      method: "tool/started",
      params: { toolName: "shell" },
    });

    expect(handler).not.toHaveBeenCalled();
  });

  it("onNotification returns unsubscribe function", async () => {
    const client = new SageClient();
    await connectClient(client, proc);

    const handler = vi.fn();
    const unsubscribe = client.onNotification("stream/delta", handler);
    unsubscribe();

    await emitServerLine(proc, {
      jsonrpc: "2.0",
      method: "stream/delta",
      params: { delta: "ignored" },
    });

    expect(handler).not.toHaveBeenCalled();
  });

  it("handles line with response and resolves pending request", async () => {
    const client = new SageClient();
    await connectClient(client, proc);

    const resultPromise = client.request("session/list");
    const request = await readNextRequest(proc);

    await emitServerLine(proc, {
      jsonrpc: "2.0",
      id: request.id,
      result: { sessions: ["s1"] },
    });

    await expect(resultPromise).resolves.toEqual({ sessions: ["s1"] });
  });

  it("handles line with notification and invokes handlers", async () => {
    const client = new SageClient();
    await connectClient(client, proc);

    const handler = vi.fn();
    client.onNotification("usage/update", handler);

    await emitServerLine(proc, {
      jsonrpc: "2.0",
      method: "usage/update",
      params: { totalCost: 0.1 },
    });

    expect(handler).toHaveBeenCalledWith({ totalCost: 0.1 });
  });

  it("skips malformed JSON lines", async () => {
    const client = new SageClient();
    await connectClient(client, proc);

    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);

    proc.stdout.write("{this is not json}\n");
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(consoleError).toHaveBeenCalled();
  });

  it("dispose rejects all pending requests", async () => {
    const client = new SageClient({ requestTimeout: 10_000 });
    await connectClient(client, proc);

    const pending = client.request("agent/run", { message: "work" });
    await readNextRequest(proc);

    client.dispose();

    await expect(pending).rejects.toThrow("Sage client disposed");
  });

  it("dispose kills subprocess", async () => {
    const client = new SageClient();
    await connectClient(client, proc);

    client.dispose();

    expect(proc.kill).toHaveBeenCalledTimes(1);
    expect(client.status).toBe("disconnected");
  });
});

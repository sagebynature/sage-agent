import { EventEmitter } from "node:events";
import { PassThrough } from "node:stream";
import { spawn } from "node:child_process";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LifecycleManager } from "../LifecycleManager.js";

vi.mock("node:child_process", () => ({
  spawn: vi.fn(),
}));

type SpawnResult = ReturnType<typeof spawn>;

interface MockProcess extends EventEmitter {
  stdin: PassThrough;
  stdout: PassThrough;
  stderr: PassThrough;
  kill: (signal?: NodeJS.Signals | number) => boolean;
  pid: number;
}

const createMockProcess = (): MockProcess => {
  return Object.assign(new EventEmitter(), {
    stdin: new PassThrough(),
    stdout: new PassThrough(),
    stderr: new PassThrough(),
    kill: vi.fn(() => true),
    pid: 54321,
  });
};

const readNextRequest = async (proc: MockProcess): Promise<Record<string, unknown>> => {
  const chunk = await new Promise<string>((resolve) => {
    proc.stdin.once("data", (data: Buffer) => resolve(data.toString("utf8")));
  });

  const line = chunk.split("\n").find((entry) => entry.trim().length > 0) ?? "";
  return JSON.parse(line) as Record<string, unknown>;
};

const emitServerResponse = async (
  proc: MockProcess,
  id: string | number,
  result: Record<string, unknown> = { ok: true },
): Promise<void> => {
  proc.stdout.write(`${JSON.stringify({ jsonrpc: "2.0", id, result })}\n`);
  await Promise.resolve();
};

describe("LifecycleManager", () => {
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

  it("startup() spawns process and sends initialize", async () => {
    const onConnected = vi.fn();
    const manager = new LifecycleManager({
      command: "sage",
      args: ["serve"],
      onConnected,
    });

    const startupPromise = manager.startup();
    const initRequest = await readNextRequest(proc);
    await emitServerResponse(proc, initRequest.id as string | number);
    await startupPromise;

    expect(mockSpawn).toHaveBeenCalledWith("sage", ["serve"], {
      stdio: ["pipe", "pipe", "pipe"],
    });
    expect(initRequest.method).toBe("initialize");
    expect(manager.isConnected).toBe(true);
    expect(onConnected).toHaveBeenCalledTimes(1);
    expect(manager.getProcess()).not.toBeNull();
  });

  it("shutdown() sends shutdown request then SIGTERM", async () => {
    vi.useFakeTimers();
    const manager = new LifecycleManager({
      command: "sage",
      args: ["serve"],
      shutdownWaitMs: 10,
      terminateWaitMs: 10,
    });

    const startupPromise = manager.startup();
    const initRequest = await readNextRequest(proc);
    await emitServerResponse(proc, initRequest.id as string | number);
    await startupPromise;

    const shutdownPromise = manager.shutdown();
    const shutdownRequest = await readNextRequest(proc);
    expect(shutdownRequest.method).toBe("shutdown");
    await emitServerResponse(proc, shutdownRequest.id as string | number);

    await vi.advanceTimersByTimeAsync(100);
    expect(proc.kill).toHaveBeenCalledWith("SIGTERM");

    await shutdownPromise;
  });

  it("calls onCrash callback on unexpected process exit", async () => {
    const onCrash = vi.fn();
    const manager = new LifecycleManager({
      command: "sage",
      args: ["serve"],
      onCrash,
    });

    const startupPromise = manager.startup();
    const initRequest = await readNextRequest(proc);
    await emitServerResponse(proc, initRequest.id as string | number);
    await startupPromise;

    proc.emit("exit", 7);

    expect(onCrash).toHaveBeenCalledWith(7);
    expect(manager.isConnected).toBe(false);
  });

  it("restart() increments crashCount and re-spawns", async () => {
    const proc2 = createMockProcess();
    mockSpawn
      .mockReturnValueOnce(proc as unknown as SpawnResult)
      .mockReturnValueOnce(proc2 as unknown as SpawnResult);

    const manager = new LifecycleManager({
      command: "sage",
      args: ["serve"],
      shutdownWaitMs: 10,
      terminateWaitMs: 10,
    });

    const startupPromise = manager.startup();
    const initRequest = await readNextRequest(proc);
    await emitServerResponse(proc, initRequest.id as string | number);
    await startupPromise;

    const restartPromise = manager.restart();
    const initRequest2 = await readNextRequest(proc2);
    await emitServerResponse(proc2, initRequest2.id as string | number);
    await restartPromise;

    expect(manager.crashCount).toBe(1);
    expect(mockSpawn).toHaveBeenCalledTimes(2);
    expect(manager.getProcess()).toBe(proc2);
  });

  it("heartbeat marks process dead after 3 ping failures", async () => {
    vi.useFakeTimers();
    const onCrash = vi.fn();
    const manager = new LifecycleManager({
      command: "sage",
      args: ["serve"],
      onCrash,
      heartbeatIntervalMs: 10,
      heartbeatTimeoutMs: 5,
      shutdownWaitMs: 10,
      terminateWaitMs: 10,
    });

    const startupPromise = manager.startup();
    const initRequest = await readNextRequest(proc);
    await emitServerResponse(proc, initRequest.id as string | number);
    await startupPromise;

    await vi.advanceTimersByTimeAsync(100);

    expect(manager.isConnected).toBe(false);
    expect(onCrash).toHaveBeenCalledTimes(1);
  });

  it("isConnected reflects lifecycle transitions", async () => {
    const manager = new LifecycleManager({ command: "sage", args: ["serve"] });
    expect(manager.isConnected).toBe(false);

    const startupPromise = manager.startup();
    const initRequest = await readNextRequest(proc);
    await emitServerResponse(proc, initRequest.id as string | number);
    await startupPromise;

    expect(manager.isConnected).toBe(true);

    const shutdownPromise = manager.shutdown();
    const shutdownRequest = await readNextRequest(proc);
    await emitServerResponse(proc, shutdownRequest.id as string | number);
    await shutdownPromise;

    expect(manager.isConnected).toBe(false);
  });
});

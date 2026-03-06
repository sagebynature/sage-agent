import { EventEmitter } from "node:events";
import { PassThrough } from "node:stream";
import { spawn } from "node:child_process";
import { createElement, createRef, type ReactNode, type RefObject } from "react";
import { Box, Text } from "ink";
import { render } from "ink-testing-library";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { EventRouter } from "../../src/integration/EventRouter.js";
import { METHODS } from "../../src/types/protocol.js";
import { getStringWidth } from "../../src/utils/string-width.js";
import { detectTheme } from "../../src/utils/theme-detect.js";
import {
  TOOL_TIMEOUT_EVENT,
  type UseToolTimeoutState,
  useToolTimeout,
} from "../../src/hooks/useToolTimeout.js";
import {
  getBackoffDelaySeconds,
  useRetryWithBackoff,
} from "../../src/hooks/useRetryWithBackoff.js";
import {
  CONTEXT_ERROR_EVENT,
  type ContextExhaustionState,
  useContextExhaustion,
} from "../../src/hooks/useContextExhaustion.js";
import {
  type MessageQueueState,
  useMessageQueue,
} from "../../src/hooks/useMessageQueue.js";
import {
  PERMISSION_TIMEOUT_EVENT,
  type PermissionTimeoutState,
  usePermissionTimeout,
} from "../../src/hooks/usePermissionTimeout.js";
import { useExitHandler } from "../../src/hooks/useExitHandler.js";
import {
  formatHiddenDelegationMessage,
  truncateDelegationChain,
} from "../../src/utils/delegation-truncate.js";
import { truncateOutput } from "../../src/utils/output-truncate.js";
import {
  MEMORY_WARNING_EVENT,
  type MemoryMonitorState,
  useMemoryMonitor,
} from "../../src/hooks/useMemoryMonitor.js";
import { useResizeHandler, type ResizeState } from "../../src/hooks/useResizeHandler.js";
import { SageClient } from "../../src/ipc/client.js";

const { mockStdout } = vi.hoisted(() => {
  const { EventEmitter: HoistedEventEmitter } = require("node:events") as typeof import("node:events");

  class MockStdout extends HoistedEventEmitter {
    columns = 120;
    rows = 40;
  }

  return { mockStdout: new MockStdout() };
});

vi.mock("ink", async () => {
  const original = await vi.importActual<typeof import("ink")>("ink");
  return {
    ...original,
    useStdout: () => ({ stdout: mockStdout, write: vi.fn() }),
  };
});

vi.mock("node:child_process", () => ({
  spawn: vi.fn(),
}));

interface ResizeHarnessProps {
  hookRef: RefObject<ResizeState | null>;
}

function ResizeHarness({ hookRef }: ResizeHarnessProps): ReactNode {
  const state = useResizeHandler();
  hookRef.current = state;
  return createElement(Text, null, `${state.width}x${state.height}:${String(state.isResizing)}`);
}

interface ToolTimeoutHarnessProps {
  callId: string;
  timeoutMs?: number;
  hookRef: RefObject<UseToolTimeoutState | null>;
}

function ToolTimeoutHarness({ callId, timeoutMs, hookRef }: ToolTimeoutHarnessProps): ReactNode {
  const state = useToolTimeout(callId, timeoutMs);
  hookRef.current = state;
  return createElement(Text, null, state.statusMessage);
}

interface RetryHarnessProps {
  hookRef: RefObject<ReturnType<typeof useRetryWithBackoff> | null>;
}

function RetryHarness({ hookRef }: RetryHarnessProps): ReactNode {
  const state = useRetryWithBackoff();
  hookRef.current = state;
  return createElement(Text, null, `${state.attempt}:${state.retryAfter}`);
}

interface ContextHarnessProps {
  hookRef: RefObject<ContextExhaustionState | null>;
}

function ContextHarness({ hookRef }: ContextHarnessProps): ReactNode {
  const state = useContextExhaustion();
  hookRef.current = state;
  return createElement(Text, null, String(state.isExhausted));
}

interface QueueHarnessProps {
  hookRef: RefObject<MessageQueueState | null>;
}

function QueueHarness({ hookRef }: QueueHarnessProps): ReactNode {
  const state = useMessageQueue();
  hookRef.current = state;
  return createElement(Text, null, `${state.queue.length}`);
}

interface PermissionHarnessProps {
  requestId: string;
  timeoutMs?: number;
  hookRef: RefObject<PermissionTimeoutState | null>;
}

function PermissionHarness({ requestId, timeoutMs, hookRef }: PermissionHarnessProps): ReactNode {
  const state = usePermissionTimeout(requestId, timeoutMs);
  hookRef.current = state;
  return createElement(Text, null, `${state.timeRemaining}:${String(state.isExpired)}`);
}

interface ExitHarnessProps {
  isStreaming: boolean;
  onCancel: () => void;
  onExit: () => void;
}

function ExitHarness({ isStreaming, onCancel, onExit }: ExitHarnessProps): ReactNode {
  useExitHandler(isStreaming, onCancel, onExit);
  return createElement(Box, null, createElement(Text, null, "exit-handler"));
}

interface MemoryHarnessProps {
  hookRef: RefObject<MemoryMonitorState | null>;
  limitMB?: number;
  intervalMs?: number;
}

function MemoryHarness({ hookRef, limitMB, intervalMs }: MemoryHarnessProps): ReactNode {
  const state = useMemoryMonitor(limitMB, intervalMs);
  hookRef.current = state;
  return createElement(Text, null, `${Math.round(state.heapUsedMB)}:${String(state.isWarning)}`);
}

type SpawnResult = ReturnType<typeof spawn>;

interface MockProcess extends EventEmitter {
  stdin: PassThrough;
  stdout: PassThrough;
  stderr: PassThrough;
  kill: () => boolean;
  pid: number;
}

function createMockProcess(): MockProcess {
  const proc = Object.assign(new EventEmitter(), {
    stdin: new PassThrough(),
    stdout: new PassThrough(),
    stderr: new PassThrough(),
    kill: () => true,
    pid: 111,
  });

  return proc;
}

async function readNextRequest(proc: MockProcess): Promise<Record<string, unknown>> {
  const chunk = await new Promise<string>((resolve) => {
    proc.stdin.once("data", (data: Buffer) => resolve(data.toString("utf8")));
  });

  const line = chunk.split("\n").find((entry) => entry.trim().length > 0) ?? "";
  return JSON.parse(line) as Record<string, unknown>;
}

async function emitServerLine(proc: MockProcess, payload: object): Promise<void> {
  proc.stdout.write(`${JSON.stringify(payload)}\n`);
  await new Promise((resolve) => setTimeout(resolve, 0));
}

describe("edge case coverage", () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    vi.useFakeTimers();
    process.env = { ...originalEnv };
    mockStdout.columns = 120;
    mockStdout.rows = 40;
    mockStdout.removeAllListeners();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
    process.env = { ...originalEnv };
  });

  test("EC-1: terminal resize during streaming", async () => {
    const hookRef = createRef<ResizeState | null>();
    render(createElement(ResizeHarness, { hookRef }));

    expect(hookRef.current?.width).toBe(120);
    mockStdout.columns = 130;
    mockStdout.rows = 41;
    mockStdout.emit("resize");

    mockStdout.columns = 150;
    mockStdout.rows = 42;
    mockStdout.emit("resize");

    await vi.advanceTimersByTimeAsync(50);
    expect(hookRef.current?.isResizing).toBe(true);
    expect(hookRef.current?.width).toBe(120);

    await vi.advanceTimersByTimeAsync(60);
    expect(hookRef.current?.isResizing).toBe(false);
    expect(hookRef.current?.width).toBe(150);
    expect(hookRef.current?.height).toBe(42);
  });

  test("EC-2: wide characters (CJK)", () => {
    expect(getStringWidth("hello")).toBe(5);
    expect(getStringWidth("你好")).toBe(4);
    expect(getStringWidth("a你b")).toBe(4);
  });

  test("EC-3: dark/light terminal detection", () => {
    process.env.COLORFGBG = "15;0";
    delete process.env.SAGE_THEME;
    expect(detectTheme()).toBe("light");

    process.env.COLORFGBG = "0;15";
    expect(detectTheme()).toBe("dark");

    process.env.SAGE_THEME = "light";
    expect(detectTheme()).toBe("light");
  });

  test("EC-4: backend crash mid-tool execution", async () => {
    const hookRef = createRef<UseToolTimeoutState | null>();
    const listener = vi.fn();
    process.on(TOOL_TIMEOUT_EVENT, listener);

    render(createElement(ToolTimeoutHarness, { callId: "call-1", timeoutMs: 30_000, hookRef }));

    await vi.advanceTimersByTimeAsync(30_000);

    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(
      expect.objectContaining({ type: "TOOL_TIMEOUT", callId: "call-1" }),
    );
    expect(hookRef.current?.isTimedOut).toBe(true);
  });

  test("EC-5: malformed JSON-RPC response", () => {
    const dispatch = vi.fn();
    const router = new EventRouter(dispatch);
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const malformed: Record<string, unknown> = {};

    Object.defineProperty(malformed, "delta", {
      enumerable: true,
      get() {
        throw new Error("garbled payload");
      },
    });

    expect(() => {
      router.handleNotification(METHODS.STREAM_DELTA, malformed);
    }).not.toThrow();
    expect(errorSpy).toHaveBeenCalledTimes(1);
    expect(dispatch).not.toHaveBeenCalled();
  });

  test("EC-6: rate limiting from LLM provider", async () => {
    expect(getBackoffDelaySeconds(1, 0.5)).toBe(1);
    expect(getBackoffDelaySeconds(2, 0.5)).toBe(2);
    expect(getBackoffDelaySeconds(3, 0.5)).toBe(4);
    expect(getBackoffDelaySeconds(4, 0.5)).toBe(8);
    expect(getBackoffDelaySeconds(5, 0.5)).toBe(16);
    expect(getBackoffDelaySeconds(6, 0.5)).toBe(30);

    const hookRef = createRef<ReturnType<typeof useRetryWithBackoff> | null>();
    render(createElement(RetryHarness, { hookRef }));

    const randomSpy = vi.spyOn(Math, "random").mockReturnValue(0.5);
    hookRef.current?.retry();
    hookRef.current?.retry();
    await vi.advanceTimersByTimeAsync(0);
    expect(hookRef.current?.attempt).toBe(2);
    expect(hookRef.current?.retryAfter).toBe(2);
    randomSpy.mockRestore();
  });

  test("EC-7: token/context exhaustion", async () => {
    const hookRef = createRef<ContextExhaustionState | null>();
    render(createElement(ContextHarness, { hookRef }));

    process.emit(CONTEXT_ERROR_EVENT, { type: "context_full", message: "context length exceeded" });
    await vi.advanceTimersByTimeAsync(0);

    expect(hookRef.current?.isExhausted).toBe(true);
    expect(hookRef.current?.options).toEqual(["compact history", "start new session"]);
  });

  test("EC-8: concurrent MCP server discovery", () => {
    const dispatched: string[] = [];
    const router = new EventRouter((action) => {
      dispatched.push(action.type);
    });

    for (let index = 0; index < 50; index += 1) {
      router.handleNotification(METHODS.DELEGATION_STARTED, {
        target: `agent-${index}`,
        task: "discover mcp",
      });
    }

    expect(dispatched).toHaveLength(50);
    expect(dispatched.every((entry) => entry === "AGENT_STARTED")).toBe(true);
  });

  test("EC-9: rapid user input during streaming", async () => {
    const hookRef = createRef<MessageQueueState | null>();
    render(createElement(QueueHarness, { hookRef }));

    hookRef.current?.enqueue("first");
    hookRef.current?.enqueue("second");
    hookRef.current?.enqueue("third");
    await vi.advanceTimersByTimeAsync(0);

    expect(hookRef.current?.queue).toEqual(["first", "second", "third"]);
    expect(hookRef.current?.indicator).toBe("Message queued — waiting for response");
    expect(hookRef.current?.flush()).toBe("first");
  });

  test("EC-10: permission timeout", async () => {
    const hookRef = createRef<PermissionTimeoutState | null>();
    const listener = vi.fn();
    process.on(PERMISSION_TIMEOUT_EVENT, listener);

    render(
      createElement(PermissionHarness, {
        requestId: "perm-1",
        timeoutMs: 60_000,
        hookRef,
      }),
    );

    await vi.advanceTimersByTimeAsync(60_000);

    expect(hookRef.current?.isExpired).toBe(true);
    expect(hookRef.current?.timeRemaining).toBe(0);
    expect(listener).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "PERMISSION_RESPOND",
        id: "perm-1",
        decision: "deny",
      }),
    );
  });

  test("EC-11: Ctrl+C handling", async () => {
    const onCancel = vi.fn();
    const onExit = vi.fn();

    const { stdin } = render(
      createElement(ExitHarness, {
        isStreaming: true,
        onCancel,
        onExit,
      }),
    );

    stdin.write("\u0003");
    await vi.advanceTimersByTimeAsync(200);
    stdin.write("\u0003");
    await vi.advanceTimersByTimeAsync(0);

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onExit).toHaveBeenCalledTimes(1);
  });

  test("EC-12: deep delegation chains (depth > 5)", () => {
    const chain = ["a", "b", "c", "d", "e", "f", "g", "h"];
    const truncated = truncateDelegationChain(chain, 5);

    expect(truncated.visible).toHaveLength(5);
    expect(truncated.hiddenCount).toBe(3);
    expect(formatHiddenDelegationMessage(truncated.hiddenCount)).toBe("... 3 more levels");
  });

  test("EC-13: long tool output (>100KB)", () => {
    const output = "x".repeat(150 * 1024);
    const result = truncateOutput(output);

    expect(result.isTruncated).toBe(true);
    expect(result.fullSize).toBe(150 * 1024);
    expect(Buffer.byteLength(result.text, "utf8")).toBeGreaterThan(10 * 1024);
    expect(result.text).toContain("truncated output");
  });

  test("EC-14: stdin conflict with spawned tools", async () => {
    vi.useRealTimers();
    const mockSpawn = vi.mocked(spawn);
    const proc = createMockProcess();
    mockSpawn.mockReturnValue(proc as unknown as SpawnResult);

    const client = new SageClient();
    const spawnPromise = client.spawn();
    const initRequest = await readNextRequest(proc);

    await emitServerLine(proc, {
      jsonrpc: "2.0",
      id: initRequest.id,
      result: { ok: true },
    });
    await spawnPromise;

    const responsePromise = client.request("session/list", { agentName: "assistant" });
    const request = await readNextRequest(proc);

    await emitServerLine(proc, {
      jsonrpc: "2.0",
      id: request.id,
      result: { sessions: [] },
    });

    await expect(responsePromise).resolves.toEqual({ sessions: [] });
    client.dispose();
    vi.useFakeTimers();
  });

  test("EC-15: OOM recovery", async () => {
    const hookRef = createRef<MemoryMonitorState | null>();
    const warningListener = vi.fn();
    process.on(MEMORY_WARNING_EVENT, warningListener);

    vi.spyOn(process, "memoryUsage").mockReturnValue({
      rss: 0,
      heapTotal: 0,
      heapUsed: 170 * 1024 * 1024,
      external: 0,
      arrayBuffers: 0,
    });

    render(createElement(MemoryHarness, { hookRef, limitMB: 200, intervalMs: 10_000 }));
    await vi.advanceTimersByTimeAsync(0);

    expect(hookRef.current?.isWarning).toBe(true);
    expect(hookRef.current?.heapUsedMB).toBeGreaterThan(160);
    expect(warningListener).toHaveBeenCalledTimes(1);
  });
});

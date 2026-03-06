import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CommandExecutor } from "../CommandExecutor.js";
import { INITIAL_STATE, type AppAction } from "../../state/AppContext.js";
import type { AppState } from "../../types/state.js";
import type { SageClient } from "../../ipc/client.js";

interface MockLifecycleManager {
  shutdown: () => Promise<void>;
}

describe("CommandExecutor", () => {
  let state: AppState;
  let dispatch: (action: AppAction) => void;
  let dispatched: AppAction[];
  let request: ReturnType<typeof vi.fn>;
  let lifecycleManager: MockLifecycleManager;

  beforeEach(() => {
    state = {
      ...INITIAL_STATE,
      session: {
        id: "session-1",
        agentName: "assistant",
        createdAt: "2026-01-01T00:00:00.000Z",
        messageCount: 2,
      },
      messages: [
        {
          id: "m1",
          role: "user",
          content: "Hello",
          timestamp: 1,
          isStreaming: false,
        },
        {
          id: "m2",
          role: "assistant",
          content: "Hi there",
          timestamp: 2,
          isStreaming: false,
        },
      ],
      usage: {
        promptTokens: 10,
        completionTokens: 20,
        totalCost: 0.01,
        model: "gpt-5",
        contextUsagePercent: 12,
      },
    };

    dispatched = [];
    dispatch = (action: AppAction) => {
      dispatched.push(action);
    };
    request = vi.fn().mockResolvedValue({ ok: true });
    lifecycleManager = {
      shutdown: vi.fn().mockResolvedValue(undefined),
    };
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const createExecutor = (): CommandExecutor => {
    const client = { request } as unknown as SageClient;
    return new CommandExecutor(
      client,
      dispatch,
      () => state,
      lifecycleManager,
    );
  };

  it("/compact sends agent/compact request", async () => {
    const executor = createExecutor();

    await executor.execute("/compact", "");

    expect(request).toHaveBeenCalledWith("agent/compact", {});
  });

  it("/tools sends tools/list request", async () => {
    const executor = createExecutor();

    await executor.execute("/tools", "");

    expect(request).toHaveBeenCalledWith("tools/list", {});
  });

  it("/usage reads local state and does not call JSON-RPC", async () => {
    const executor = createExecutor();

    const result = await executor.execute("/usage", "");

    expect(request).not.toHaveBeenCalled();
    expect(result).toContain("promptTokens: 10");
    expect(result).toContain("completionTokens: 20");
  });

  it("/session dispatches SET_VIEW", async () => {
    const executor = createExecutor();

    await executor.execute("/session", "");

    expect(dispatched).toContainEqual({ type: "SET_VIEW", view: "dashboard" });
    expect(request).not.toHaveBeenCalled();
  });

  it("/export returns markdown transcript", async () => {
    const executor = createExecutor();

    const result = await executor.execute("/export", "");

    expect(result).toContain("# Session Export");
    expect(result).toContain("## User");
    expect(result).toContain("Hello");
    expect(result).toContain("## Assistant");
    expect(result).toContain("Hi there");
  });

  it("/quit calls lifecycle shutdown then exits process", async () => {
    const exitSpy = vi
      .spyOn(process, "exit")
      .mockImplementation((() => undefined) as (code?: string | number | null) => never);
    const executor = createExecutor();

    await executor.execute("/quit", "");

    expect(lifecycleManager.shutdown).toHaveBeenCalledTimes(1);
    expect(exitSpy).toHaveBeenCalledWith(0);
  });

  it("unknown command warns and performs no-op", async () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const executor = createExecutor();

    const result = await executor.execute("/does-not-exist", "");

    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(request).not.toHaveBeenCalled();
    expect(result).toBeUndefined();
  });

  it("/clear sends session/clear and resets session messageCount", async () => {
    const executor = createExecutor();

    await executor.execute("/clear", "");

    expect(request).toHaveBeenCalledWith("session/clear", { sessionId: "session-1" });
    expect(dispatched).toContainEqual({
      type: "SET_SESSION",
      session: {
        id: "session-1",
        agentName: "assistant",
        createdAt: "2026-01-01T00:00:00.000Z",
        messageCount: 0,
      },
    });
  });

  it("/model sends config/get request", async () => {
    const executor = createExecutor();

    await executor.execute("/model", "");

    expect(request).toHaveBeenCalledWith("config/get", { key: "model" });
  });

  it("/sessions sends session/list request", async () => {
    const executor = createExecutor();

    await executor.execute("/sessions", "");

    expect(request).toHaveBeenCalledWith("session/list", {});
  });

  it("/help returns command list text", async () => {
    const executor = createExecutor();

    const result = await executor.execute("/help", "");

    expect(result).toContain("/help");
    expect(result).toContain("/quit");
  });

  it("/reset calls session clear and dispatches full reset actions", async () => {
    const executor = createExecutor();

    await executor.execute("/reset", "");

    expect(request).toHaveBeenCalledWith("session/clear", {});
    expect(dispatched).toContainEqual({ type: "SET_SESSION", session: null });
    expect(dispatched).toContainEqual({ type: "SET_STREAMING", isStreaming: false });
    expect(dispatched).toContainEqual({ type: "CLEAR_ERROR" });
  });

  it("handles /models command", async () => {
    request.mockResolvedValueOnce({ value: "gpt-4" });
    const executor = createExecutor();
    const result = await executor.execute("models", "");
    expect(request).toHaveBeenCalledWith("config/get", { key: "model" });
    expect(typeof result).toBe("string");
  });

  it("handles /permissions command with no pending", async () => {
    const executor = createExecutor();
    const result = await executor.execute("permissions", "");
    expect(result).toBe("No pending permission requests.");
  });

  it("handles /theme command", async () => {
    const executor = createExecutor();
    const result = await executor.execute("theme", "");
    expect(typeof result).toBe("string");
  });

  it("handles /split command toggles view", async () => {
    const executor = createExecutor();
    await executor.execute("split", "");
    const actions = dispatched.map((a) => a.type);
    expect(actions).toContain("SET_VIEW");
  });

  it("handles /agent command with no active agents", async () => {
    const executor = createExecutor();
    const result = await executor.execute("agent", "");
    expect(result).toBe("No active agents.");
  });

  it("handles /agents command with no agents", async () => {
    const executor = createExecutor();
    const result = await executor.execute("agents", "");
    expect(result).toBe("No agents.");
  });

  it("handles /plan command", async () => {
    const executor = createExecutor();
    const result = await executor.execute("plan", "");
    expect(typeof result).toBe("string");
  });

  it("handles /notepad command", async () => {
    const executor = createExecutor();
    const result = await executor.execute("notepad", "");
    expect(typeof result).toBe("string");
  });

  it("handles /bg command", async () => {
    const executor = createExecutor();
    const result = await executor.execute("bg", "");
    expect(typeof result).toBe("string");
  });

  it("handles /diff command", async () => {
    const executor = createExecutor();
    const result = await executor.execute("diff", "");
    expect(typeof result).toBe("string");
  });
});

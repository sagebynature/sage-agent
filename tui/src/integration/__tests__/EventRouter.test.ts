import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createEventRouter } from "../EventRouter.js";
import { METHODS } from "../../types/protocol.js";
import type { AppAction } from "../../state/AppContext.js";

describe("EventRouter", () => {
  let dispatched: AppAction[];
  let dispatch: (action: AppAction) => void;

  beforeEach(() => {
    dispatched = [];
    dispatch = (action: AppAction) => {
      dispatched.push(action);
    };
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("maps tool/started notification to TOOL_STARTED action", () => {
    vi.spyOn(Date, "now").mockReturnValue(1000);
    const router = createEventRouter(dispatch);

    router.handleNotification(METHODS.TOOL_STARTED, {
      callId: "call-1",
      toolName: "shell",
      arguments: { command: "ls" },
    });

    expect(dispatched).toEqual([
      {
        type: "TOOL_STARTED",
        tool: {
          id: "call-1",
          name: "shell",
          status: "running",
          arguments: { command: "ls" },
          startedAt: 1000,
        },
      },
    ]);
  });

  it("maps tool/completed notification to TOOL_COMPLETED action", () => {
    const router = createEventRouter(dispatch);

    router.handleNotification(METHODS.TOOL_COMPLETED, {
      callId: "call-1",
      result: "ok",
      error: "",
    });

    expect(dispatched).toEqual([
      {
        type: "TOOL_COMPLETED",
        id: "call-1",
        result: "ok",
      },
    ]);
  });

  it("creates streaming message and sets streaming on first stream delta", () => {
    vi.spyOn(Date, "now").mockReturnValue(2000);
    const router = createEventRouter(dispatch);

    router.handleNotification(METHODS.STREAM_DELTA, {
      turn: 1,
      delta: "Hello",
    });

    expect(dispatched).toHaveLength(2);
    expect(dispatched[0]).toMatchObject({
      type: "ADD_MESSAGE",
      message: {
        role: "assistant",
        content: "Hello",
        timestamp: 2000,
        isStreaming: true,
      },
    });
    expect(dispatched[1]).toEqual({ type: "SET_STREAMING", isStreaming: true });
  });

  it("accumulates content across stream deltas and updates existing message", () => {
    vi.useFakeTimers();
    const router = createEventRouter(dispatch);

    router.handleNotification(METHODS.STREAM_DELTA, {
      turn: 1,
      delta: "Hello",
    });
    router.handleNotification(METHODS.STREAM_DELTA, {
      turn: 1,
      delta: " world",
    });

    expect(
      dispatched.some((action) => action.type === "UPDATE_MESSAGE"),
    ).toBe(false);

    vi.advanceTimersByTime(16);

    const updateAction = dispatched.find(
      (action): action is Extract<AppAction, { type: "UPDATE_MESSAGE" }> =>
        action.type === "UPDATE_MESSAGE",
    );
    expect(updateAction).toBeDefined();
    expect(updateAction?.updates.content).toBe("Hello world");
  });

  it("resets stream accumulator when turn changes", () => {
    const router = createEventRouter(dispatch);

    router.handleNotification(METHODS.STREAM_DELTA, {
      turn: 1,
      delta: "first",
    });
    router.handleNotification(METHODS.STREAM_DELTA, {
      turn: 2,
      delta: "second",
    });

    const addActions = dispatched.filter(
      (action): action is Extract<AppAction, { type: "ADD_MESSAGE" }> =>
        action.type === "ADD_MESSAGE",
    );

    expect(addActions).toHaveLength(2);
    expect(addActions[0]?.message.content).toBe("first");
    expect(addActions[1]?.message.content).toBe("second");
  });

  it("maps delegation notifications to AGENT actions", () => {
    vi.spyOn(Date, "now").mockReturnValue(3000);
    const router = createEventRouter(dispatch);

    router.handleNotification(METHODS.DELEGATION_STARTED, {
      target: "researcher",
      task: "find docs",
    });
    router.handleNotification(METHODS.DELEGATION_COMPLETED, {
      target: "researcher",
      result: "done",
    });

    expect(dispatched).toEqual([
      {
        type: "AGENT_STARTED",
        agent: {
          name: "researcher",
          status: "active",
          task: "find docs",
          depth: 1,
          children: [],
          startedAt: 3000,
        },
      },
      {
        type: "AGENT_COMPLETED",
        name: "researcher",
        status: "completed",
      },
    ]);
  });

  it("maps background/completed notification", () => {
    const router = createEventRouter(dispatch);

    router.handleNotification(METHODS.BACKGROUND_COMPLETED, {
      taskId: "bg-1",
      status: "completed",
      result: "ok",
      error: undefined,
    });

    expect(dispatched).toEqual([
      {
        type: "BACKGROUND_TASK_UPDATE",
        taskId: "bg-1",
        status: "completed",
        result: "ok",
      },
    ]);
  });

  it("maps permission/request notification", () => {
    const router = createEventRouter(dispatch);

    router.handleNotification(METHODS.PERMISSION_REQUEST, {
      requestId: "perm-1",
      tool: "shell",
      arguments: { command: "rm -rf /tmp" },
      command: "rm -rf /tmp",
      riskLevel: "high",
    });

    expect(dispatched).toEqual([
      {
        type: "PERMISSION_REQUEST",
        permission: {
          id: "perm-1",
          tool: "shell",
          arguments: { command: "rm -rf /tmp" },
          command: "rm -rf /tmp",
          riskLevel: "high",
          status: "pending",
        },
      },
    ]);
  });

  it("maps usage/update and compaction/started notifications", () => {
    const router = createEventRouter(dispatch);

    router.handleNotification(METHODS.USAGE_UPDATE, {
      promptTokens: 10,
      completionTokens: 20,
      totalCost: 0.5,
      model: "gpt-5",
      contextUsagePercent: 42,
    });

    router.handleNotification(METHODS.COMPACTION_STARTED, {
      reason: "threshold exceeded",
      beforeTokens: 30000,
    });

    expect(dispatched).toEqual([
      {
        type: "UPDATE_USAGE",
        usage: {
          promptTokens: 10,
          completionTokens: 20,
          totalCost: 0.5,
          model: "gpt-5",
          contextUsagePercent: 42,
        },
      },
      {
        type: "COMPACTION_STARTED",
        reason: "threshold exceeded",
      },
    ]);
  });

  it("maps error notification to SET_ERROR action", () => {
    const router = createEventRouter(dispatch);

    router.handleNotification(METHODS.ERROR, {
      code: "oops",
      message: "bad things",
      recoverable: false,
    });

    expect(dispatched).toEqual([{ type: "SET_ERROR", error: "bad things" }]);
  });

  it("warns for unknown notification methods", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const router = createEventRouter(dispatch);

    router.handleNotification("unknown/method", { value: 1 });

    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(dispatched).toHaveLength(0);
  });

  it("maps run/completed success to SET_STREAMING false and finalizes message", () => {
    const router = createEventRouter(dispatch);

    // Simulate an active stream first
    router.handleNotification(METHODS.STREAM_DELTA, { delta: "hi", turn: 1 });

    dispatched.length = 0; // clear previous dispatches

    router.handleNotification(METHODS.RUN_COMPLETED, {
      runId: "run-1",
      status: "success",
    });

    const types = dispatched.map((a) => a.type);
    expect(types).toContain("SET_STREAMING");
    const streamingAction = dispatched.find((a) => a.type === "SET_STREAMING");
    expect(streamingAction).toEqual({ type: "SET_STREAMING", isStreaming: false });
  });

  it("maps run/completed error to SET_STREAMING false and SET_ERROR", () => {
    const router = createEventRouter(dispatch);

    router.handleNotification(METHODS.RUN_COMPLETED, {
      runId: "run-2",
      status: "error",
      error: "model exploded",
    });

    const types = dispatched.map((a) => a.type);
    expect(types).toContain("SET_STREAMING");
    expect(types).toContain("SET_ERROR");
    const errorAction = dispatched.find((a) => a.type === "SET_ERROR");
    expect(errorAction).toEqual({ type: "SET_ERROR", error: "model exploded" });
  });

  it("maps run/completed cancelled to SET_STREAMING false without error", () => {
    const router = createEventRouter(dispatch);

    router.handleNotification(METHODS.RUN_COMPLETED, {
      runId: "run-3",
      status: "cancelled",
    });

    const types = dispatched.map((a) => a.type);
    expect(types).toContain("SET_STREAMING");
    expect(types).not.toContain("SET_ERROR");
  });
});

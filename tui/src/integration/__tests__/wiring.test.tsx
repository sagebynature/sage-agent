import { beforeEach, describe, expect, it, vi } from "vitest";
import { wireIntegration } from "../wiring.js";
import { CommandExecutor } from "../CommandExecutor.js";
import { EventRouter } from "../EventRouter.js";
import { METHODS } from "../../types/protocol.js";
import { INITIAL_STATE, type AppAction } from "../../state/AppContext.js";
import type { SageClient } from "../../ipc/client.js";

type NotificationHandler = (params: Record<string, unknown>) => void;

interface MockClientBundle {
  client: SageClient;
  request: ReturnType<typeof vi.fn>;
  onNotification: ReturnType<typeof vi.fn>;
  emit: (method: string, params: Record<string, unknown>) => void;
}

function createMockClient(): MockClientBundle {
  const handlers = new Map<string, Set<NotificationHandler>>();
  const request = vi.fn().mockResolvedValue({ ok: true });
  const onNotification = vi.fn((method: string, handler: NotificationHandler) => {
    const existing = handlers.get(method) ?? new Set<NotificationHandler>();
    existing.add(handler);
    handlers.set(method, existing);

    return () => {
      const current = handlers.get(method);
      if (!current) {
        return;
      }

      current.delete(handler);
      if (current.size === 0) {
        handlers.delete(method);
      }
    };
  });

  const client = {
    request,
    onNotification,
  } as unknown as SageClient;

  const emit = (method: string, params: Record<string, unknown>): void => {
    const current = handlers.get(method);
    if (!current) {
      return;
    }

    for (const handler of current) {
      handler(params);
    }
  };

  return {
    client,
    request,
    onNotification,
    emit,
  };
}

describe("wireIntegration", () => {
  let dispatch: ReturnType<typeof vi.fn<(action: AppAction) => void>>;
  let getState: () => typeof INITIAL_STATE;

  beforeEach(() => {
    dispatch = vi.fn();
    getState = () => INITIAL_STATE;
  });

  it("creates EventRouter and CommandExecutor", () => {
    const { client } = createMockClient();

    const result = wireIntegration({ client, dispatch, getState });

    expect(result.eventRouter).toBeInstanceOf(EventRouter);
    expect(result.commandExecutor).toBeInstanceOf(CommandExecutor);
    expect(typeof result.cleanup).toBe("function");
  });

  it("registers handlers for all protocol notification methods", () => {
    const { client, onNotification } = createMockClient();

    wireIntegration({ client, dispatch, getState });

    const registered = onNotification.mock.calls.map((call) => call[0]);
    expect(registered).toEqual([
      METHODS.STREAM_DELTA,
      METHODS.TOOL_STARTED,
      METHODS.TOOL_COMPLETED,
      METHODS.DELEGATION_STARTED,
      METHODS.DELEGATION_COMPLETED,
      METHODS.BACKGROUND_COMPLETED,
      METHODS.PERMISSION_REQUEST,
      METHODS.USAGE_UPDATE,
      METHODS.COMPACTION_STARTED,
      METHODS.ERROR,
      METHODS.RUN_COMPLETED,
    ]);
  });

  it("routes stream/delta notification to ADD_MESSAGE dispatch", () => {
    const { client, emit } = createMockClient();
    wireIntegration({ client, dispatch, getState });

    emit(METHODS.STREAM_DELTA, { turn: 1, delta: "hello" });

    const actionTypes = dispatch.mock.calls.map(([action]) => action.type);
    expect(actionTypes).toContain("ADD_MESSAGE");
  });

  it("routes tool/started notification to TOOL_STARTED dispatch", () => {
    const { client, emit } = createMockClient();
    wireIntegration({ client, dispatch, getState });

    emit(METHODS.TOOL_STARTED, {
      callId: "call-1",
      toolName: "shell",
      arguments: { command: "ls" },
    });

    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "TOOL_STARTED",
      }),
    );
  });

  it("routes tool/completed notification to TOOL_COMPLETED dispatch", () => {
    const { client, emit } = createMockClient();
    wireIntegration({ client, dispatch, getState });

    emit(METHODS.TOOL_COMPLETED, {
      callId: "call-1",
      toolName: "shell",
      result: "done",
      durationMs: 20,
    });

    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "TOOL_COMPLETED",
        id: "call-1",
      }),
    );
  });

  it("routes permission/request notification to PERMISSION_REQUEST dispatch", () => {
    const { client, emit } = createMockClient();
    wireIntegration({ client, dispatch, getState });

    emit(METHODS.PERMISSION_REQUEST, {
      requestId: "perm-1",
      tool: "shell",
      arguments: { command: "ls" },
      riskLevel: "high",
    });

    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "PERMISSION_REQUEST",
      }),
    );
  });

  it("routes usage/update notification to UPDATE_USAGE dispatch", () => {
    const { client, emit } = createMockClient();
    wireIntegration({ client, dispatch, getState });

    emit(METHODS.USAGE_UPDATE, {
      promptTokens: 1,
      completionTokens: 2,
      totalCost: 0.01,
      model: "gpt-5",
      contextUsagePercent: 33,
    });

    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "UPDATE_USAGE",
      }),
    );
  });

  it("routes error notification to SET_ERROR dispatch", () => {
    const { client, emit } = createMockClient();
    wireIntegration({ client, dispatch, getState });

    emit(METHODS.ERROR, {
      code: "err",
      message: "boom",
      recoverable: false,
    });

    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "SET_ERROR",
        error: "boom",
      }),
    );
  });

  it("routes delegation notifications to AGENT_STARTED and AGENT_COMPLETED", () => {
    const { client, emit } = createMockClient();
    wireIntegration({ client, dispatch, getState });

    emit(METHODS.DELEGATION_STARTED, {
      target: "researcher",
      task: "collect docs",
    });
    emit(METHODS.DELEGATION_COMPLETED, {
      target: "researcher",
      result: "done",
    });

    const actionTypes = dispatch.mock.calls.map(([action]) => action.type);
    expect(actionTypes).toContain("AGENT_STARTED");
    expect(actionTypes).toContain("AGENT_COMPLETED");
  });

  it("routes background/completed notification to BACKGROUND_TASK_UPDATE", () => {
    const { client, emit } = createMockClient();
    wireIntegration({ client, dispatch, getState });

    emit(METHODS.BACKGROUND_COMPLETED, {
      taskId: "bg-1",
      agentName: "helper",
      status: "completed",
      result: "ok",
    });

    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "BACKGROUND_TASK_UPDATE",
        taskId: "bg-1",
      }),
    );
  });

  it("cleanup unsubscribes all notification handlers", () => {
    const { client, emit } = createMockClient();
    const { cleanup } = wireIntegration({ client, dispatch, getState });

    cleanup();
    emit(METHODS.ERROR, {
      code: "err",
      message: "should not dispatch",
      recoverable: false,
    });
    emit(METHODS.STREAM_DELTA, {
      turn: 1,
      delta: "ignored",
    });

    expect(dispatch).not.toHaveBeenCalled();
  });

  it("routes run/completed notification to SET_STREAMING false", () => {
    const { client, emit } = createMockClient();
    wireIntegration({ client, dispatch, getState });

    emit(METHODS.RUN_COMPLETED, {
      runId: "run-1",
      status: "success",
    });

    const actionTypes = dispatch.mock.calls.map(([action]) => action.type);
    expect(actionTypes).toContain("SET_STREAMING");
  });

  it("wires CommandExecutor with provided client and dispatch", async () => {
    const { client, request } = createMockClient();
    const { commandExecutor } = wireIntegration({ client, dispatch, getState });

    await commandExecutor.execute("/tools", "");
    await commandExecutor.execute("/session", "");

    expect(request).toHaveBeenCalledWith("tools/list", {});
    expect(dispatch).toHaveBeenCalledWith({ type: "SET_VIEW", view: "dashboard" });
  });
});

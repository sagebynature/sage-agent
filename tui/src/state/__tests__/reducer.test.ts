import { describe, it, expect } from "vitest";
import { appReducer, INITIAL_STATE } from "../AppContext.js";
import type { AppAction } from "../AppContext.js";
import type {
  ChatMessage,
  ToolCallState,
  PermissionState,
  SessionState,
  AgentNode,
} from "../../types/state.js";

const makeMessage = (overrides: Partial<ChatMessage> = {}): ChatMessage => ({
  id: "msg-1",
  role: "user",
  content: "hello",
  timestamp: 1000,
  isStreaming: false,
  ...overrides,
});

const makeTool = (overrides: Partial<ToolCallState> = {}): ToolCallState => ({
  id: "tool-1",
  name: "shell",
  status: "running",
  arguments: { cmd: "ls" },
  ...overrides,
});

const makePermission = (
  overrides: Partial<PermissionState> = {},
): PermissionState => ({
  id: "perm-1",
  tool: "shell",
  arguments: { cmd: "rm -rf" },
  riskLevel: "high",
  status: "pending",
  ...overrides,
});

const makeSession = (overrides: Partial<SessionState> = {}): SessionState => ({
  id: "sess-1",
  agentName: "assistant",
  createdAt: "2026-01-01",
  messageCount: 0,
  ...overrides,
});

const makeAgent = (overrides: Partial<AgentNode> = {}): AgentNode => ({
  name: "agent-1",
  status: "active",
  depth: 0,
  children: [],
  ...overrides,
});

describe("appReducer", () => {
  it("ADD_MESSAGE appends message to messages array", () => {
    const message = makeMessage();
    const action: AppAction = { type: "ADD_MESSAGE", message };
    const state = appReducer(INITIAL_STATE, action);
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]).toBe(message);
  });

  it("UPDATE_MESSAGE updates the matching message by id", () => {
    const message = makeMessage({ id: "msg-42", content: "original" });
    const withMessage = appReducer(INITIAL_STATE, {
      type: "ADD_MESSAGE",
      message,
    });
    const updated = appReducer(withMessage, {
      type: "UPDATE_MESSAGE",
      id: "msg-42",
      updates: { content: "updated", isStreaming: true },
    });
    expect(updated.messages[0]?.content).toBe("updated");
    expect(updated.messages[0]?.isStreaming).toBe(true);
  });

  it("UPDATE_MESSAGE leaves non-matching messages unchanged", () => {
    const msg1 = makeMessage({ id: "msg-1", content: "first" });
    const msg2 = makeMessage({ id: "msg-2", content: "second" });
    let state = appReducer(INITIAL_STATE, { type: "ADD_MESSAGE", message: msg1 });
    state = appReducer(state, { type: "ADD_MESSAGE", message: msg2 });
    state = appReducer(state, {
      type: "UPDATE_MESSAGE",
      id: "msg-1",
      updates: { content: "modified" },
    });
    expect(state.messages[0]?.content).toBe("modified");
    expect(state.messages[1]?.content).toBe("second");
  });

  it("SET_STREAMING sets isStreaming to true", () => {
    const state = appReducer(INITIAL_STATE, {
      type: "SET_STREAMING",
      isStreaming: true,
    });
    expect(state.isStreaming).toBe(true);
  });

  it("SET_STREAMING sets isStreaming to false", () => {
    const streaming = { ...INITIAL_STATE, isStreaming: true };
    const state = appReducer(streaming, {
      type: "SET_STREAMING",
      isStreaming: false,
    });
    expect(state.isStreaming).toBe(false);
  });

  it("TOOL_STARTED appends tool to tools array", () => {
    const tool = makeTool();
    const state = appReducer(INITIAL_STATE, { type: "TOOL_STARTED", tool });
    expect(state.tools).toHaveLength(1);
    expect(state.tools[0]).toBe(tool);
  });

  it("TOOL_COMPLETED marks tool as completed with result", () => {
    const tool = makeTool({ id: "tool-99", status: "running" });
    let state = appReducer(INITIAL_STATE, { type: "TOOL_STARTED", tool });
    state = appReducer(state, {
      type: "TOOL_COMPLETED",
      id: "tool-99",
      result: "success output",
    });
    expect(state.tools[0]?.status).toBe("completed");
    expect(state.tools[0]?.result).toBe("success output");
    expect(state.tools[0]?.completedAt).toBeGreaterThan(0);
  });

  it("TOOL_COMPLETED marks tool as failed when error provided", () => {
    const tool = makeTool({ id: "tool-err", status: "running" });
    let state = appReducer(INITIAL_STATE, { type: "TOOL_STARTED", tool });
    state = appReducer(state, {
      type: "TOOL_COMPLETED",
      id: "tool-err",
      error: "command failed",
    });
    expect(state.tools[0]?.status).toBe("failed");
    expect(state.tools[0]?.error).toBe("command failed");
  });

  it("PERMISSION_REQUEST appends permission to permissions array", () => {
    const permission = makePermission();
    const state = appReducer(INITIAL_STATE, {
      type: "PERMISSION_REQUEST",
      permission,
    });
    expect(state.permissions).toHaveLength(1);
    expect(state.permissions[0]).toBe(permission);
  });

  it("PERMISSION_RESPOND sets status to approved for allow_once", () => {
    const permission = makePermission({ id: "perm-x" });
    let state = appReducer(INITIAL_STATE, {
      type: "PERMISSION_REQUEST",
      permission,
    });
    state = appReducer(state, {
      type: "PERMISSION_RESPOND",
      id: "perm-x",
      decision: "allow_once",
    });
    expect(state.permissions[0]?.status).toBe("approved");
  });

  it("PERMISSION_RESPOND sets status to denied for deny", () => {
    const permission = makePermission({ id: "perm-y" });
    let state = appReducer(INITIAL_STATE, {
      type: "PERMISSION_REQUEST",
      permission,
    });
    state = appReducer(state, {
      type: "PERMISSION_RESPOND",
      id: "perm-y",
      decision: "deny",
    });
    expect(state.permissions[0]?.status).toBe("denied");
  });

  it("SET_SESSION replaces the session", () => {
    const session = makeSession();
    const state = appReducer(INITIAL_STATE, { type: "SET_SESSION", session });
    expect(state.session).toBe(session);
  });

  it("SET_SESSION with null clears the session", () => {
    const withSession = { ...INITIAL_STATE, session: makeSession() };
    const state = appReducer(withSession, { type: "SET_SESSION", session: null });
    expect(state.session).toBeNull();
  });

  it("UPDATE_USAGE merges partial usage update", () => {
    const state = appReducer(INITIAL_STATE, {
      type: "UPDATE_USAGE",
      usage: { promptTokens: 500, totalCost: 0.0012 },
    });
    expect(state.usage.promptTokens).toBe(500);
    expect(state.usage.totalCost).toBe(0.0012);
    expect(state.usage.completionTokens).toBe(0);
  });

  it("SET_ERROR sets the error string", () => {
    const state = appReducer(INITIAL_STATE, {
      type: "SET_ERROR",
      error: "something went wrong",
    });
    expect(state.error).toBe("something went wrong");
  });

  it("CLEAR_ERROR sets error to null", () => {
    const withError = { ...INITIAL_STATE, error: "oops" };
    const state = appReducer(withError, { type: "CLEAR_ERROR" });
    expect(state.error).toBeNull();
  });

  it("SET_VIEW updates currentView", () => {
    const state = appReducer(INITIAL_STATE, {
      type: "SET_VIEW",
      view: "dashboard",
    });
    expect(state.currentView).toBe("dashboard");
  });

  it("AGENT_STARTED appends agent to agents array", () => {
    const agent = makeAgent();
    const state = appReducer(INITIAL_STATE, { type: "AGENT_STARTED", agent });
    expect(state.agents).toHaveLength(1);
    expect(state.agents[0]).toBe(agent);
  });

  it("AGENT_COMPLETED marks agent as completed", () => {
    const agent = makeAgent({ name: "worker", status: "active" });
    let state = appReducer(INITIAL_STATE, { type: "AGENT_STARTED", agent });
    state = appReducer(state, {
      type: "AGENT_COMPLETED",
      name: "worker",
      status: "completed",
    });
    expect(state.agents[0]?.status).toBe("completed");
    expect(state.agents[0]?.completedAt).toBeGreaterThan(0);
  });

  it("AGENT_COMPLETED marks agent as failed", () => {
    const agent = makeAgent({ name: "flaky", status: "active" });
    let state = appReducer(INITIAL_STATE, { type: "AGENT_STARTED", agent });
    state = appReducer(state, {
      type: "AGENT_COMPLETED",
      name: "flaky",
      status: "failed",
    });
    expect(state.agents[0]?.status).toBe("failed");
  });

  it("BACKGROUND_TASK_UPDATE returns state unchanged", () => {
    const state = appReducer(INITIAL_STATE, {
      type: "BACKGROUND_TASK_UPDATE",
      taskId: "task-1",
      status: "running",
    });
    expect(state).toBe(INITIAL_STATE);
  });

  it("COMPACTION_STARTED returns state unchanged", () => {
    const state = appReducer(INITIAL_STATE, {
      type: "COMPACTION_STARTED",
      reason: "context limit reached",
    });
    expect(state).toBe(INITIAL_STATE);
  });
});

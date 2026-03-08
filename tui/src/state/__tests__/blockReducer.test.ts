import { describe, it, expect } from "vitest";
import { blockReducer, INITIAL_BLOCK_STATE } from "../blockReducer.js";
import type { BlockAction } from "../blockReducer.js";
import type { PermissionState, AgentNode } from "../../types/state.js";
import type { EventRecord } from "../../types/events.js";

function makeEvent(overrides: Partial<EventRecord> = {}): EventRecord {
  return {
    id: overrides.id ?? "event-1",
    eventName: overrides.eventName ?? "pre_tool_execute",
    category: overrides.category ?? "tool",
    phase: overrides.phase ?? "start",
    status: overrides.status,
    timestamp: overrides.timestamp ?? 1,
    agentName: overrides.agentName ?? "sage",
    agentPath: overrides.agentPath ?? ["sage"],
    runId: overrides.runId,
    turnId: overrides.turnId,
    turnIndex: overrides.turnIndex,
    sessionId: overrides.sessionId,
    originatingSessionId: overrides.originatingSessionId,
    parentEventId: overrides.parentEventId,
    triggerEventId: overrides.triggerEventId,
    traceId: overrides.traceId,
    spanId: overrides.spanId,
    durationMs: overrides.durationMs,
    usage: overrides.usage,
    payload: overrides.payload ?? {},
    error: overrides.error,
    sourceMethod: overrides.sourceMethod,
    summary: overrides.summary ?? "summary",
  };
}

describe("blockReducer", () => {
  it("SUBMIT_MESSAGE appends user block", () => {
    const action: BlockAction = { type: "SUBMIT_MESSAGE", content: "hello" };
    const state = blockReducer(INITIAL_BLOCK_STATE, action);
    expect(state.completedBlocks).toHaveLength(1);
    expect(state.completedBlocks[0]!.type).toBe("user");
    expect(state.completedBlocks[0]!.content).toBe("hello");
    expect(state.completedBlocks[0]!.id).toMatch(/^user_/);
  });

  it("STREAM_START creates activeStream with isThinking true", () => {
    const action: BlockAction = { type: "STREAM_START", runId: "run-1" };
    const state = blockReducer(INITIAL_BLOCK_STATE, action);
    expect(state.activeStream).not.toBeNull();
    expect(state.activeStream!.runId).toBe("run-1");
    expect(state.activeStream!.isThinking).toBe(true);
    expect(state.activeStream!.content).toBe("");
    expect(state.activeStream!.tools).toEqual([]);
  });

  it("STREAM_DELTA appends content and clears isThinking", () => {
    const withStream = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    const state = blockReducer(withStream, {
      type: "STREAM_DELTA",
      delta: "Hello ",
    });
    expect(state.activeStream!.content).toBe("Hello ");
    expect(state.activeStream!.isThinking).toBe(false);

    const state2 = blockReducer(state, {
      type: "STREAM_DELTA",
      delta: "world",
    });
    expect(state2.activeStream!.content).toBe("Hello world");
  });

  it("STREAM_DELTA auto-creates activeStream when none exists", () => {
    const state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_DELTA",
      delta: "orphan",
    });
    expect(state.activeStream).not.toBeNull();
    expect(state.activeStream!.content).toBe("orphan");
    expect(state.activeStream!.isThinking).toBe(false);
  });

  it("TOOL_STARTED adds running tool to activeStream", () => {
    const withStream = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    const state = blockReducer(withStream, {
      type: "TOOL_STARTED",
      name: "read_file",
      callId: "call-1",
      arguments: { path: "/foo" },
    });
    expect(state.activeStream!.tools).toHaveLength(1);
    expect(state.activeStream!.tools[0]).toMatchObject({
      name: "read_file",
      callId: "call-1",
      arguments: { path: "/foo" },
      status: "running",
    });
    expect(state.activeStream!.tools[0]!.startedAt).toBeDefined();
  });

  it("TOOL_COMPLETED updates tool status to completed", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    state = blockReducer(state, {
      type: "TOOL_STARTED",
      name: "read_file",
      callId: "call-1",
      arguments: {},
    });
    state = blockReducer(state, {
      type: "TOOL_COMPLETED",
      callId: "call-1",
      result: "file contents",
      durationMs: 150,
    });
    const tool = state.activeStream!.tools[0]!;
    expect(tool.status).toBe("completed");
    expect(tool.result).toBe("file contents");
    expect(tool.durationMs).toBe(150);
    expect(tool.error).toBeUndefined();
  });

  it("TOOL_COMPLETED updates tool status to failed when error present", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    state = blockReducer(state, {
      type: "TOOL_STARTED",
      name: "write_file",
      callId: "call-2",
      arguments: {},
    });
    state = blockReducer(state, {
      type: "TOOL_COMPLETED",
      callId: "call-2",
      error: "Permission denied",
    });
    const tool = state.activeStream!.tools[0]!;
    expect(tool.status).toBe("failed");
    expect(tool.error).toBe("Permission denied");
  });

  it("STREAM_END flattens to completedBlocks (tool + text)", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    state = blockReducer(state, {
      type: "TOOL_STARTED",
      name: "read_file",
      callId: "call-1",
      arguments: { path: "/foo" },
    });
    state = blockReducer(state, {
      type: "TOOL_COMPLETED",
      callId: "call-1",
      result: "contents",
    });
    state = blockReducer(state, {
      type: "STREAM_DELTA",
      delta: "Here is the file.",
    });
    state = blockReducer(state, {
      type: "STREAM_END",
      status: "success",
    });

    expect(state.activeStream).toBeNull();
    expect(state.completedBlocks).toHaveLength(2);
    expect(state.completedBlocks[0]!.type).toBe("tool");
    expect(state.completedBlocks[0]!.content).toBe("read_file");
    expect(state.completedBlocks[0]!.tools).toHaveLength(1);
    expect(state.completedBlocks[1]!.type).toBe("text");
    expect(state.completedBlocks[1]!.content).toBe("Here is the file.");
  });

  it("STREAM_END with error appends error block", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    state = blockReducer(state, {
      type: "STREAM_DELTA",
      delta: "partial ",
    });
    state = blockReducer(state, {
      type: "STREAM_END",
      status: "error",
      error: "Connection lost",
    });

    expect(state.activeStream).toBeNull();
    // text block from "partial " + error block
    expect(state.completedBlocks).toHaveLength(2);
    expect(state.completedBlocks[0]!.type).toBe("text");
    expect(state.completedBlocks[0]!.content).toBe("partial");
    expect(state.completedBlocks[1]!.type).toBe("error");
    expect(state.completedBlocks[1]!.content).toBe("Connection lost");
  });

  it("UPDATE_USAGE updates usage state", () => {
    const state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "UPDATE_USAGE",
      usage: { promptTokens: 100, model: "gpt-4" },
    });
    expect(state.usage.promptTokens).toBe(100);
    expect(state.usage.model).toBe("gpt-4");
    expect(state.usage.completionTokens).toBe(0);
    expect(state.usage.totalCost).toBe(0);
  });

  it("SET_ERROR sets error and CLEAR_ERROR clears it", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "SET_ERROR",
      error: "Something broke",
    });
    expect(state.error).toBe("Something broke");

    state = blockReducer(state, { type: "CLEAR_ERROR" });
    expect(state.error).toBeNull();
  });

  it("PERMISSION_REQUEST adds permission and PERMISSION_RESPOND updates status", () => {
    const permission: PermissionState = {
      id: "perm-1",
      tool: "bash",
      arguments: { command: "rm -rf /" },
      riskLevel: "high",
      status: "pending",
    };

    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "PERMISSION_REQUEST",
      permission,
    });
    expect(state.permissions).toHaveLength(1);
    expect(state.permissions[0]!.status).toBe("pending");

    // approve
    state = blockReducer(state, {
      type: "PERMISSION_RESPOND",
      id: "perm-1",
      decision: "allow_once",
    });
    expect(state.permissions[0]!.status).toBe("approved");

    // add another and deny
    const perm2: PermissionState = {
      id: "perm-2",
      tool: "write",
      arguments: {},
      riskLevel: "medium",
      status: "pending",
    };
    state = blockReducer(state, {
      type: "PERMISSION_REQUEST",
      permission: perm2,
    });
    state = blockReducer(state, {
      type: "PERMISSION_RESPOND",
      id: "perm-2",
      decision: "deny",
    });
    expect(state.permissions[1]!.status).toBe("denied");
  });

  it("SET_SESSION replaces session", () => {
    const session = {
      id: "sess-1",
      agentName: "sage",
      createdAt: "2026-03-06",
      messageCount: 5,
    };
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "SET_SESSION",
      session,
    });
    expect(state.session).toEqual(session);

    state = blockReducer(state, { type: "SET_SESSION", session: null });
    expect(state.session).toBeNull();
  });

  it("STREAM_END force-resolves running tools to completed", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    state = blockReducer(state, {
      type: "TOOL_STARTED",
      name: "delegate → researcher",
      callId: "del-1",
      arguments: { task: "search" },
    });
    // Tool never gets TOOL_COMPLETED — simulate stream ending while tool still running
    state = blockReducer(state, {
      type: "STREAM_END",
      status: "success",
    });

    expect(state.activeStream).toBeNull();
    const toolBlock = state.completedBlocks.find((b) => b.type === "tool");
    expect(toolBlock).toBeDefined();
    expect(toolBlock!.tools![0]!.status).toBe("completed");
  });

  it("STREAM_END with cancelled status marks running tools as cancelled", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    state = blockReducer(state, {
      type: "TOOL_STARTED",
      name: "shell",
      callId: "call-1",
      arguments: {},
    });
    state = blockReducer(state, {
      type: "STREAM_END",
      status: "cancelled",
    });

    const toolBlock = state.completedBlocks.find((b) => b.type === "tool");
    expect(toolBlock!.tools![0]!.status).toBe("failed");
    expect(toolBlock!.tools![0]!.error).toBe("cancelled");
  });

  it("ADD_SYSTEM_BLOCK appends system block", () => {
    const state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "ADD_SYSTEM_BLOCK",
      content: "Agent initialized",
    });
    expect(state.completedBlocks).toHaveLength(1);
    expect(state.completedBlocks[0]!.type).toBe("system");
    expect(state.completedBlocks[0]!.content).toBe("Agent initialized");
    expect(state.completedBlocks[0]!.id).toMatch(/^system_/);
  });

  it("AGENT_STARTED adds agent to agents array", () => {
    const agent: AgentNode = {
      name: "researcher",
      status: "active",
      task: "find docs",
      depth: 1,
      children: [],
      startedAt: 1000,
    };
    const state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "AGENT_STARTED",
      agent,
    });
    expect(state.agents).toHaveLength(1);
    expect(state.agents[0]!.name).toBe("researcher");
  });

  it("AGENT_COMPLETED updates agent status", () => {
    const agent: AgentNode = {
      name: "researcher",
      status: "active",
      task: "find docs",
      depth: 1,
      children: [],
      startedAt: 1000,
    };
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "AGENT_STARTED",
      agent,
    });
    state = blockReducer(state, {
      type: "AGENT_COMPLETED",
      name: "researcher",
      status: "completed",
    });
    expect(state.agents[0]!.status).toBe("completed");
    expect(state.agents[0]!.completedAt).toBeDefined();
  });

  it("CLEAR_BLOCKS resets completedBlocks, activeStream, agents, scrollOffset, and prunes permissions", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "SUBMIT_MESSAGE",
      content: "hello",
    });
    state = blockReducer(state, {
      type: "PERMISSION_REQUEST",
      permission: { id: "p1", tool: "bash", arguments: {}, riskLevel: "high", status: "pending" },
    });
    state = blockReducer(state, {
      type: "PERMISSION_RESPOND",
      id: "p1",
      decision: "allow_once",
    });
    state = blockReducer(state, { type: "SCROLL_UP", lines: 5 });
    state = blockReducer(state, { type: "CLEAR_BLOCKS" });

    expect(state.completedBlocks).toEqual([]);
    expect(state.activeStream).toBeNull();
    expect(state.permissions).toEqual([]);
    expect(state.agents).toEqual([]);
    expect(state.error).toBeNull();
    expect(state.scrollOffset).toBe(0);
    expect(state.completedRunIds.size).toBe(0);
  });

  it("STREAM_START is ignored for an already-completed run (phantom stream guard)", () => {
    // Simulate the race: events complete a run, then a late STREAM_START arrives
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    state = blockReducer(state, {
      type: "STREAM_DELTA",
      delta: "Hello world",
    });
    state = blockReducer(state, {
      type: "STREAM_END",
      status: "success",
    });

    // Content should be in completedBlocks, activeStream is null
    expect(state.activeStream).toBeNull();
    expect(state.completedBlocks).toHaveLength(1);
    expect(state.completedBlocks[0]!.content).toBe("Hello world");
    expect(state.completedRunIds.has("run-1")).toBe(true);

    // Late STREAM_START for the same runId — should be a no-op
    const stateAfterLateStart = blockReducer(state, {
      type: "STREAM_START",
      runId: "run-1",
    });
    expect(stateAfterLateStart.activeStream).toBeNull();
    expect(stateAfterLateStart.completedBlocks).toHaveLength(1);
  });

  it("STREAM_END records runId in completedRunIds", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-42",
    });
    state = blockReducer(state, {
      type: "STREAM_DELTA",
      delta: "test",
    });
    state = blockReducer(state, {
      type: "STREAM_END",
      status: "success",
    });
    expect(state.completedRunIds.has("run-42")).toBe(true);
  });

  it("STREAM_END prunes resolved permissions", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "PERMISSION_REQUEST",
      permission: { id: "p1", tool: "bash", arguments: {}, riskLevel: "high", status: "pending" },
    });
    state = blockReducer(state, {
      type: "PERMISSION_RESPOND",
      id: "p1",
      decision: "allow_once",
    });
    state = blockReducer(state, {
      type: "PERMISSION_REQUEST",
      permission: { id: "p2", tool: "read", arguments: {}, riskLevel: "low", status: "pending" },
    });
    state = blockReducer(state, {
      type: "STREAM_START",
      runId: "run-1",
    });
    state = blockReducer(state, {
      type: "STREAM_END",
      status: "success",
    });

    // p1 (approved) pruned, p2 (still pending) kept
    expect(state.permissions).toHaveLength(1);
    expect(state.permissions[0]!.id).toBe("p2");
  });

  it("SCROLL_UP increases scrollOffset", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, { type: "SCROLL_UP" });
    expect(state.scrollOffset).toBe(1);
    state = blockReducer(state, { type: "SCROLL_UP", lines: 5 });
    expect(state.scrollOffset).toBe(6);
  });

  it("SCROLL_DOWN decreases scrollOffset but not below 0", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, { type: "SCROLL_UP", lines: 3 });
    state = blockReducer(state, { type: "SCROLL_DOWN", lines: 2 });
    expect(state.scrollOffset).toBe(1);
    state = blockReducer(state, { type: "SCROLL_DOWN", lines: 5 });
    expect(state.scrollOffset).toBe(0);
  });

  it("SCROLL_TO_BOTTOM resets scrollOffset to 0", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, { type: "SCROLL_UP", lines: 10 });
    state = blockReducer(state, { type: "SCROLL_TO_BOTTOM" });
    expect(state.scrollOffset).toBe(0);
  });

  it("STREAM_DELTA resets scrollOffset to 0", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, { type: "SCROLL_UP", lines: 5 });
    expect(state.scrollOffset).toBe(5);
    state = blockReducer(state, { type: "STREAM_DELTA", delta: "hello" });
    expect(state.scrollOffset).toBe(0);
  });

  it("event navigation respects current filters", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, { type: "SET_VERBOSITY", verbosity: "debug" });
    state = blockReducer(state, { type: "EVENT_RECEIVED", event: makeEvent({ id: "tool-1", category: "tool" }) });
    state = blockReducer(state, { type: "EVENT_RECEIVED", event: makeEvent({ id: "llm-1", category: "llm", eventName: "pre_llm_call" }) });
    state = blockReducer(state, {
      type: "SET_EVENT_FILTERS",
      filters: { categories: ["llm"] },
    });

    expect(state.ui.selectedEventId).toBe("llm-1");
    state = blockReducer(state, { type: "SELECT_PREV_EVENT" });
    expect(state.ui.selectedEventId).toBe("llm-1");
  });

  it("changing filters reselects a visible event", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, { type: "SET_VERBOSITY", verbosity: "debug" });
    state = blockReducer(state, { type: "EVENT_RECEIVED", event: makeEvent({ id: "tool-1", category: "tool" }) });
    state = blockReducer(state, { type: "SELECT_EVENT", eventId: "tool-1" });
    state = blockReducer(state, {
      type: "SET_EVENT_FILTERS",
      filters: { categories: ["llm"] },
    });

    expect(state.ui.selectedEventId).toBeNull();
    state = blockReducer(state, {
      type: "EVENT_RECEIVED",
      event: makeEvent({ id: "llm-1", category: "llm", eventName: "pre_llm_call" }),
    });
    expect(state.ui.selectedEventId).toBe("llm-1");
  });
});

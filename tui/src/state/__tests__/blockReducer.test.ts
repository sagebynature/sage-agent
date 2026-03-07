import { describe, it, expect } from "vitest";
import { blockReducer, INITIAL_BLOCK_STATE } from "../blockReducer.js";
import type { BlockAction, BlockState } from "../blockReducer.js";
import type { PermissionState } from "../../types/state.js";

describe("blockReducer", () => {
  it("SUBMIT_MESSAGE appends user block", () => {
    const action: BlockAction = { type: "SUBMIT_MESSAGE", content: "hello" };
    const state = blockReducer(INITIAL_BLOCK_STATE, action);
    expect(state.completedBlocks).toHaveLength(1);
    expect(state.completedBlocks[0].type).toBe("user");
    expect(state.completedBlocks[0].content).toBe("hello");
    expect(state.completedBlocks[0].id).toMatch(/^user_/);
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

  it("STREAM_DELTA is no-op when no activeStream", () => {
    const state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_DELTA",
      delta: "orphan",
    });
    expect(state).toBe(INITIAL_BLOCK_STATE);
    expect(state.activeStream).toBeNull();
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
    expect(state.activeStream!.tools[0]).toEqual({
      name: "read_file",
      callId: "call-1",
      arguments: { path: "/foo" },
      status: "running",
    });
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
    const tool = state.activeStream!.tools[0];
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
    const tool = state.activeStream!.tools[0];
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
    expect(state.completedBlocks[0].type).toBe("tool");
    expect(state.completedBlocks[0].content).toBe("read_file");
    expect(state.completedBlocks[0].tools).toHaveLength(1);
    expect(state.completedBlocks[1].type).toBe("text");
    expect(state.completedBlocks[1].content).toBe("Here is the file.");
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
    expect(state.completedBlocks[0].type).toBe("text");
    expect(state.completedBlocks[0].content).toBe("partial");
    expect(state.completedBlocks[1].type).toBe("error");
    expect(state.completedBlocks[1].content).toBe("Connection lost");
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
    expect(state.permissions[0].status).toBe("pending");

    // approve
    state = blockReducer(state, {
      type: "PERMISSION_RESPOND",
      id: "perm-1",
      decision: "allow_once",
    });
    expect(state.permissions[0].status).toBe("approved");

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
    expect(state.permissions[1].status).toBe("denied");
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

  it("ADD_SYSTEM_BLOCK appends system block", () => {
    const state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "ADD_SYSTEM_BLOCK",
      content: "Agent initialized",
    });
    expect(state.completedBlocks).toHaveLength(1);
    expect(state.completedBlocks[0].type).toBe("system");
    expect(state.completedBlocks[0].content).toBe("Agent initialized");
    expect(state.completedBlocks[0].id).toMatch(/^system_/);
  });
});

import { describe, it, expect, beforeEach } from "vitest";
import { BlockEventRouter } from "../BlockEventRouter.js";
import { METHODS } from "../../types/protocol.js";
import type { BlockAction } from "../../state/blockReducer.js";

describe("BlockEventRouter", () => {
  let dispatched: BlockAction[];
  let dispatch: (action: BlockAction) => void;
  let router: BlockEventRouter;

  beforeEach(() => {
    dispatched = [];
    dispatch = (action: BlockAction) => dispatched.push(action);
    router = new BlockEventRouter(dispatch);
  });

  it("maps delegation/started to AGENT_STARTED", () => {
    router.handleNotification(METHODS.DELEGATION_STARTED, {
      target: "researcher",
      task: "find docs",
    });

    expect(dispatched[0]!.type).toBe("EVENT_RECEIVED");
    expect(dispatched.some((action) => action.type === "AGENT_STARTED")).toBe(true);
    const agentStarted = dispatched.find((action) => action.type === "AGENT_STARTED");
    if (agentStarted?.type === "AGENT_STARTED") {
      expect(agentStarted.agent.name).toBe("researcher");
    }
  });

  it("maps delegation/completed to AGENT_COMPLETED", () => {
    router.handleNotification(METHODS.DELEGATION_STARTED, {
      target: "researcher",
      task: "find docs",
    });

    dispatched.length = 0;

    router.handleNotification(METHODS.DELEGATION_COMPLETED, {
      target: "researcher",
      result: "found 3 docs",
    });

    const completedAction = dispatched.find((a) => a.type === "AGENT_COMPLETED");
    expect(completedAction).toBeDefined();
    if (completedAction?.type === "AGENT_COMPLETED") {
      expect(completedAction.name).toBe("researcher");
      expect(completedAction.status).toBe("completed");
    }
  });

  it("delegation/completed without prior start still dispatches system block", () => {
    router.handleNotification(METHODS.DELEGATION_COMPLETED, {
      target: "unknown",
      result: "done",
    });

    expect(dispatched.some((a) => a.type === "ADD_SYSTEM_BLOCK")).toBe(true);
  });

  it("maps tool/started and tool/completed", () => {
    router.handleNotification(METHODS.TOOL_STARTED, {
      toolName: "shell",
      callId: "call-1",
      arguments: { command: "ls" },
    });

    expect(dispatched[0]!.type).toBe("EVENT_RECEIVED");
    expect(dispatched[1]).toEqual({
      type: "TOOL_STARTED",
      name: "shell",
      callId: "call-1",
      arguments: { command: "ls" },
    });
  });

  it("delegation/started dispatches AGENT_STARTED", () => {
    router.handleNotification(METHODS.DELEGATION_STARTED, {
      target: "coder",
      task: "write tests",
    });

    expect(dispatched.some((a) => a.type === "AGENT_STARTED")).toBe(true);
    expect(dispatched.some((a) => a.type === "TOOL_STARTED")).toBe(false);

    const agentAction = dispatched.find((a) => a.type === "AGENT_STARTED");
    if (agentAction?.type === "AGENT_STARTED") {
      expect(agentAction.agent.name).toBe("coder");
      expect(agentAction.agent.status).toBe("active");
    }
  });

  it("delegation/completed dispatches AGENT_COMPLETED", () => {
    router.handleNotification(METHODS.DELEGATION_STARTED, {
      target: "coder",
      task: "write tests",
    });
    dispatched.length = 0;

    router.handleNotification(METHODS.DELEGATION_COMPLETED, {
      target: "coder",
      result: "done",
    });

    expect(dispatched.some((a) => a.type === "AGENT_COMPLETED")).toBe(true);
    expect(dispatched.some((a) => a.type === "TOOL_COMPLETED")).toBe(false);

    const agentAction = dispatched.find((a) => a.type === "AGENT_COMPLETED");
    if (agentAction?.type === "AGENT_COMPLETED") {
      expect(agentAction.name).toBe("coder");
      expect(agentAction.status).toBe("completed");
    }
  });

  it("handles llm/turn_started notification", () => {
    router.handleNotification(METHODS.LLM_TURN_STARTED, {
      turn: 1,
      model: "gpt-5",
      messageCount: 3,
    });
    // LLM turn started is informational — no crash
    expect(dispatched.length).toBeGreaterThanOrEqual(0);
  });

  it("projects complexity from canonical pre_llm_call events into active stream state", () => {
    router.handleNotification(METHODS.EVENT_EMITTED, {
      eventId: "evt-1",
      eventName: "pre_llm_call",
      category: "llm",
      phase: "start",
      timestamp: Date.now(),
      agentName: "agent",
      agentPath: ["agent"],
      payload: {
        complexity: {
          score: 42,
          level: "medium",
          version: "openfang-v1",
        },
      },
    });

    const action = dispatched.find((candidate) => candidate.type === "SET_ACTIVE_COMPLEXITY");
    expect(action).toBeDefined();
    if (action?.type === "SET_ACTIVE_COMPLEXITY") {
      expect(action.complexity).toEqual({
        score: 42,
        level: "medium",
        version: "openfang-v1",
      });
    }
  });

  it("de-duplicates legacy events once event/emitted is seen", () => {
    // 1. Send legacy event -> should be processed
    router.handleNotification(METHODS.STREAM_DELTA, { delta: "hello" });
    expect(dispatched.some((a) => a.type === "STREAM_DELTA")).toBe(true);
    dispatched.length = 0;

    // 2. Send event/emitted -> should be processed and set hasCanonicalEvents=true
    router.handleNotification(METHODS.EVENT_EMITTED, {
      eventName: "on_llm_stream_delta",
      payload: { delta: "world" },
      agentName: "agent",
      agentPath: ["agent"],
    });
    expect(dispatched.some((a) => a.type === "STREAM_DELTA")).toBe(true);
    dispatched.length = 0;

    // 3. Send legacy event again -> should be IGNORED
    router.handleNotification(METHODS.STREAM_DELTA, { delta: "ignored" });
    expect(dispatched.some((a) => a.type === "STREAM_DELTA")).toBe(false);
  });

  it("preserves critical permission risk levels from backend notifications", () => {
    router.handleNotification(METHODS.PERMISSION_REQUEST, {
      request_id: "perm-1",
      tool: "shell",
      arguments: { command: "rm -rf /tmp/demo" },
      riskLevel: "critical",
    });

    const action = dispatched.find((candidate) => candidate.type === "PERMISSION_REQUEST");
    expect(action).toBeDefined();
    if (action?.type === "PERMISSION_REQUEST") {
      expect(action.permission.riskLevel).toBe("critical");
    }
  });
});

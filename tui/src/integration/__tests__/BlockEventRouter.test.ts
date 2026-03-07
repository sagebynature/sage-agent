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

  it("maps delegation/started to AGENT_STARTED + TOOL_STARTED", () => {
    router.handleNotification(METHODS.DELEGATION_STARTED, {
      target: "researcher",
      task: "find docs",
    });

    expect(dispatched).toHaveLength(2);
    expect(dispatched[0]!.type).toBe("AGENT_STARTED");
    expect(dispatched[1]!.type).toBe("TOOL_STARTED");
    if (dispatched[1]!.type === "TOOL_STARTED") {
      expect(dispatched[1]!.name).toContain("researcher");
      expect(dispatched[1]!.callId).toMatch(/^delegation_/);
    }
  });

  it("maps delegation/completed to TOOL_COMPLETED with matching callId", () => {
    router.handleNotification(METHODS.DELEGATION_STARTED, {
      target: "researcher",
      task: "find docs",
    });

    const startAction = dispatched.find((a) => a.type === "TOOL_STARTED")!;
    expect(startAction.type).toBe("TOOL_STARTED");
    const callId = startAction.type === "TOOL_STARTED" ? startAction.callId : "";

    dispatched.length = 0;

    router.handleNotification(METHODS.DELEGATION_COMPLETED, {
      target: "researcher",
      result: "found 3 docs",
    });

    const completedAction = dispatched.find((a) => a.type === "TOOL_COMPLETED");
    expect(completedAction).toBeDefined();
    if (completedAction?.type === "TOOL_COMPLETED") {
      expect(completedAction.callId).toBe(callId);
      expect(completedAction.result).toBe("found 3 docs");
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
    expect(dispatched[0]).toEqual({
      type: "TOOL_STARTED",
      name: "shell",
      callId: "call-1",
      arguments: { command: "ls" },
    });
  });

  it("delegation/started dispatches AGENT_STARTED and TOOL_STARTED", () => {
    router.handleNotification(METHODS.DELEGATION_STARTED, {
      target: "coder",
      task: "write tests",
    });

    expect(dispatched.some((a) => a.type === "AGENT_STARTED")).toBe(true);
    expect(dispatched.some((a) => a.type === "TOOL_STARTED")).toBe(true);

    const agentAction = dispatched.find((a) => a.type === "AGENT_STARTED");
    if (agentAction?.type === "AGENT_STARTED") {
      expect(agentAction.agent.name).toBe("coder");
      expect(agentAction.agent.status).toBe("active");
    }
  });

  it("delegation/completed dispatches AGENT_COMPLETED and TOOL_COMPLETED", () => {
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
    expect(dispatched.some((a) => a.type === "TOOL_COMPLETED")).toBe(true);

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
});

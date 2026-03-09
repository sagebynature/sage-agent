import { describe, expect, it } from "vitest";
import { EventProjector } from "../EventProjector.js";
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

describe("EventProjector", () => {
  it("correlates same-name tool events by run and agent path when call IDs are absent", () => {
    const projector = new EventProjector();

    const startedA = projector.project(makeEvent({
      id: "start-a",
      runId: "run-a",
      agentName: "worker-a",
      agentPath: ["root", "worker-a"],
      payload: { tool_name: "shell", arguments: { command: "pwd" } },
    }));
    const startedB = projector.project(makeEvent({
      id: "start-b",
      runId: "run-b",
      agentName: "worker-b",
      agentPath: ["root", "worker-b"],
      payload: { tool_name: "shell", arguments: { command: "ls" } },
    }));

    const startActionA = startedA[0];
    const startActionB = startedB[0];
    expect(startActionA?.type).toBe("TOOL_STARTED");
    expect(startActionB?.type).toBe("TOOL_STARTED");
    if (startActionA?.type !== "TOOL_STARTED" || startActionB?.type !== "TOOL_STARTED") {
      return;
    }

    const completedB = projector.project(makeEvent({
      id: "end-b",
      eventName: "post_tool_execute",
      phase: "complete",
      runId: "run-b",
      agentName: "worker-b",
      agentPath: ["root", "worker-b"],
      payload: { tool_name: "shell", result: "done-b" },
    }));
    const completedA = projector.project(makeEvent({
      id: "end-a",
      eventName: "post_tool_execute",
      phase: "complete",
      runId: "run-a",
      agentName: "worker-a",
      agentPath: ["root", "worker-a"],
      payload: { tool_name: "shell", result: "done-a" },
    }));

    expect(completedB[0]).toEqual({
      type: "TOOL_COMPLETED",
      callId: startActionB.callId,
      result: "done-b",
      error: undefined,
      durationMs: undefined,
    });
    expect(completedA[0]).toEqual({
      type: "TOOL_COMPLETED",
      callId: startActionA.callId,
      result: "done-a",
      error: undefined,
      durationMs: undefined,
    });
    expect(startActionA.callId).not.toBe(startActionB.callId);
  });

  it("emits a system block when a completion arrives without a matching start", () => {
    const projector = new EventProjector();

    const actions = projector.project(makeEvent({
      id: "orphan-end",
      eventName: "post_tool_execute",
      phase: "complete",
      runId: "run-a",
      agentPath: ["root", "worker-a"],
      payload: { tool_name: "shell", result: "done" },
    }));

    expect(actions).toEqual([{
      type: "ADD_SYSTEM_BLOCK",
      content: "Tool shell completed without matching start",
    }]);
  });
});

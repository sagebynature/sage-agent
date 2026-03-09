import { describe, expect, it } from "vitest";
import {
  buildInspectorLines,
  resolveScrollbarRange,
  visibleInspectorLines,
} from "../EventInspector.js";
import type { EventRecord } from "../../types/events.js";

function createEvent(payload: Record<string, unknown>): EventRecord {
  return {
    id: "event-1",
    eventName: "post_tool_execute",
    category: "tool",
    phase: "complete",
    status: "ok",
    timestamp: Date.now(),
    agentName: "sage",
    agentPath: ["sage"],
    payload,
    summary: "tool completed",
    runId: "run-1",
    sessionId: "session-1",
    turnIndex: 2,
  };
}

describe("EventInspector helpers", () => {
  it("builds full inspector content without truncating payload lines", () => {
    const event = createEvent({
      nested: {
        items: Array.from({ length: 12 }, (_, index) => `value-${index}`),
      },
    });

    const lines = buildInspectorLines(event);
    expect(lines[0]?.text).toBe("tool completed");
    expect(lines.some((line) => line.text.includes("value-11"))).toBe(true);
    expect(lines.some((line) => line.text === "payload:")).toBe(true);
  });

  it("returns the requested visible window", () => {
    const lines = Array.from({ length: 10 }, (_, index) => ({ text: `line-${index}` }));
    expect(visibleInspectorLines(lines, 4, 3).map((line) => line.text)).toEqual([
      "line-4",
      "line-5",
      "line-6",
    ]);
  });

  it("computes a scrollbar thumb for overflowing content", () => {
    expect(resolveScrollbarRange(20, 5, 10)).toEqual({
      thumbStart: 3,
      thumbSize: 1,
    });
  });
});

import { describe, expect, it } from "vitest";
import { render } from "ink-testing-library";
import { EventTimeline } from "../EventTimeline.js";
import type { EventRecord } from "../../types/events.js";

function makeEvent(index: number): EventRecord {
  return {
    id: `event-${index}`,
    eventName: "pre_tool_execute",
    category: "tool",
    phase: "start",
    timestamp: index,
    agentName: "sage",
    agentPath: ["sage"],
    payload: {},
    summary: `event ${index}`,
  };
}

describe("EventTimeline", () => {
  it("keeps the selected event visible when it falls outside the trailing window", () => {
    const events = Array.from({ length: 10 }, (_, index) => makeEvent(index));

    const { lastFrame } = render(
      <EventTimeline
        events={events}
        selectedEventId="event-2"
        limit={4}
      />,
    );

    const frame = lastFrame() ?? "";
    expect(frame).toContain("event 2");
    expect(frame).not.toContain("event 9");
  });
});

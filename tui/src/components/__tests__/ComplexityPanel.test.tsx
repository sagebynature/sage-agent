import { describe, expect, it } from "vitest";
import { render } from "ink-testing-library";
import { ComplexityPanel } from "../ComplexityPanel.js";
import type { EventRecord } from "../../types/events.js";

function makeEvent(payload: Record<string, unknown>): EventRecord {
  return {
    id: "evt-1",
    eventName: "pre_llm_call",
    category: "llm",
    phase: "start",
    timestamp: Date.now(),
    agentName: "agent",
    agentPath: ["agent"],
    payload,
    summary: "turn 0 started",
  };
}

describe("ComplexityPanel", () => {
  it("renders empty state when no event is selected", () => {
    const { lastFrame } = render(<ComplexityPanel event={null} />);
    expect(lastFrame() ?? "").toContain("No complexity data");
  });

  it("renders score and factor breakdown", () => {
    const event = makeEvent({
      complexity: {
        score: 9136,
        level: "complex",
        version: "openfang-v1",
        metadata: {
          message_chars: 8700,
          tool_count: 12,
          message_count: 15,
        },
        factors: [
          { kind: "message_length", contribution: 8700, value: 8700 },
          { kind: "tool_count", contribution: 240, value: 12 },
        ],
      },
    });
    const { lastFrame } = render(<ComplexityPanel event={event} />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("Complexity Score");
    expect(frame).toContain("C9136 complex");
    expect(frame).toContain("8700 chars | 12 tools | 15");
    expect(frame).toContain("msgs");
    expect(frame).toContain("message length +8700");
    expect(frame).toContain("tools +240");
  });
});

import { describe, expect, it } from "vitest";
import { render } from "ink-testing-library";
import { ActiveTaskDock } from "../ActiveTaskDock.js";
import type { ActiveStream } from "../../types/blocks.js";

function makeStream(runId: string, content: string): ActiveStream {
  return {
    runId,
    content,
    tools: [],
    isThinking: false,
    startedAt: Date.now(),
  };
}

describe("ActiveTaskDock", () => {
  it("renders nothing when there are no active streams", () => {
    const { lastFrame } = render(<ActiveTaskDock streams={[]} />);
    expect(lastFrame()).toBe("");
  });

  it("renders active streams in LIFO order nearest the bottom", () => {
    const first = makeStream("run-1", "older task");
    const second = makeStream("run-2", "newer task");

    const { lastFrame } = render(<ActiveTaskDock streams={[first, second]} />);
    const frame = lastFrame() ?? "";

    expect(frame).toContain("Active Tasks");
    expect(frame.indexOf("newer task")).toBeLessThan(frame.indexOf("older task"));
  });

  it("hides completed tool rows and keeps only running tools in the dock", () => {
    const stream: ActiveStream = {
      runId: "run-1",
      content: "",
      isThinking: false,
      startedAt: Date.now(),
      tools: [
        {
          name: "delegate",
          callId: "call-1",
          arguments: { agent_name: "researcher", task: "Research day trading strategies" },
          status: "running",
        },
        {
          name: "web_search",
          callId: "call-2",
          arguments: { query: "day trading strategies" },
          result: "search results",
          status: "completed",
        },
        {
          name: "web_fetch",
          callId: "call-3",
          arguments: { url: "https://example.com" },
          status: "running",
        },
      ],
    };

    const { lastFrame } = render(<ActiveTaskDock streams={[stream]} />);
    const frame = lastFrame() ?? "";

    expect(frame).toContain("delegate");
    expect(frame).toContain("web_fetch");
    expect(frame).not.toContain("web_search");
    expect(frame).not.toContain("search results");
  });
});

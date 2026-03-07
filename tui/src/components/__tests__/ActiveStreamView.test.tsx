import { describe, it, expect, vi } from "vitest";
import { render } from "ink-testing-library";

import { ActiveStreamView } from "../ActiveStreamView.js";
import type { ActiveStream } from "../../types/blocks.js";

describe("ActiveStreamView", () => {
  it("shows thinking indicator when isThinking", () => {
    const stream: ActiveStream = {
      runId: "r1",
      content: "",
      tools: [],
      isThinking: true,
      startedAt: Date.now(),
    };
    const { lastFrame } = render(<ActiveStreamView stream={stream} />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("Thinking");
  });

  it("renders streaming content after debounce", async () => {
    vi.useFakeTimers();
    const stream: ActiveStream = {
      runId: "r1",
      content: "Hello world",
      tools: [],
      isThinking: false,
      startedAt: Date.now(),
    };
    const { lastFrame } = render(<ActiveStreamView stream={stream} />);

    // Advance past the 16ms debounce
    await vi.advanceTimersByTimeAsync(50);

    const frame = lastFrame() ?? "";
    expect(frame).toContain("Hello world");
    vi.useRealTimers();
  });

  it("shows running tool", () => {
    const stream: ActiveStream = {
      runId: "r1",
      content: "",
      tools: [
        {
          name: "Read",
          callId: "c1",
          arguments: { path: "file.txt" },
          status: "running",
        },
      ],
      isThinking: false,
      startedAt: Date.now(),
    };
    const { lastFrame } = render(<ActiveStreamView stream={stream} />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("Read");
    expect(frame).toContain("running");
  });

  it("returns null when stream is null", () => {
    const { lastFrame } = render(<ActiveStreamView stream={null} />);
    expect(lastFrame()).toBe("");
  });
});

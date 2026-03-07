import { describe, it, expect } from "vitest";
import { render } from "ink-testing-library";

import { ActiveStreamView, truncateStreamLines } from "../ActiveStreamView.js";
import type { ActiveStream } from "../../types/blocks.js";

describe("truncateStreamLines", () => {
  it("returns all lines when under limit", () => {
    const content = "line1\nline2\nline3";
    const { lines, truncatedCount } = truncateStreamLines(content, 30);
    expect(lines).toHaveLength(3);
    expect(truncatedCount).toBe(0);
  });

  it("truncates to last N lines when over limit", () => {
    const content = Array.from({ length: 50 }, (_, i) => `line${i}`).join("\n");
    const { lines, truncatedCount } = truncateStreamLines(content, 30);
    expect(lines).toHaveLength(30);
    expect(truncatedCount).toBe(20);
    expect(lines[0]).toBe("line20");
    expect(lines[29]).toBe("line49");
  });
});

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

  it("renders streaming content as plain text immediately", () => {
    const stream: ActiveStream = {
      runId: "r1",
      content: "Hello world",
      tools: [],
      isThinking: false,
      startedAt: Date.now(),
    };
    const { lastFrame } = render(<ActiveStreamView stream={stream} />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("Hello world");
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
    expect(frame).toContain("file.txt");
  });

  it("returns null when stream is null", () => {
    const { lastFrame } = render(<ActiveStreamView stream={null} />);
    expect(lastFrame()).toBe("");
  });
});

import { describe, it, expect } from "vitest";
import { render } from "ink-testing-library";

import { StaticBlock } from "../StaticBlock.js";
import type { OutputBlock } from "../../../types/blocks.js";

describe("StaticBlock", () => {
  it("renders user block with dimmed > prefix", () => {
    const block: OutputBlock = {
      id: "u1",
      type: "user",
      content: "hello world",
      timestamp: 1000,
    };
    const { lastFrame } = render(<StaticBlock block={block} />);
    expect(lastFrame()).toContain(">");
    expect(lastFrame()).toContain("hello world");
  });

  it("renders text block without a bullet prefix and preserves markdown text", () => {
    const block: OutputBlock = {
      id: "t1",
      type: "text",
      content: "some **bold** text",
      timestamp: 1000,
    };
    const { lastFrame } = render(<StaticBlock block={block} />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("some");
    expect(frame).not.toContain("● some");
  });

  it("renders tool block with summary", () => {
    const block: OutputBlock = {
      id: "tool1",
      type: "tool",
      content: "Read",
      tools: [
        {
          name: "Read",
          callId: "c1",
          arguments: { path: "file.txt" },
          status: "completed",
          durationMs: 150,
        },
      ],
      timestamp: 1000,
    };
    const { lastFrame } = render(<StaticBlock block={block} />);
    expect(lastFrame()).toContain("●");
    expect(lastFrame()).toContain("Read");
  });

  it("renders error block in red", () => {
    const block: OutputBlock = {
      id: "e1",
      type: "error",
      content: "something broke",
      timestamp: 1000,
    };
    const { lastFrame } = render(<StaticBlock block={block} />);
    expect(lastFrame()).toContain("something broke");
  });

  it("renders system block dimmed", () => {
    const block: OutputBlock = {
      id: "s1",
      type: "system",
      content: "compaction started",
      timestamp: 1000,
    };
    const { lastFrame } = render(<StaticBlock block={block} />);
    expect(lastFrame()).toContain("compaction started");
  });
});

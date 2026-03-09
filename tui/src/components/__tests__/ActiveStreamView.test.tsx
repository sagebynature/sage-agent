import { describe, it, expect } from "vitest";
import { render } from "ink-testing-library";

import {
  ActiveStreamView,
  resolveActiveLabelStyles,
  resolveActiveStatusStyle,
  resolveSweepPosition,
  truncateStreamLines,
} from "../ActiveStreamView.js";
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
  it("bounces the sweep position across the label width", () => {
    expect([0, 1, 2, 3, 4, 5, 6].map((phase) => resolveSweepPosition(phase, 4))).toEqual([
      0,
      1,
      2,
      3,
      2,
      1,
      0,
    ]);
    expect(resolveSweepPosition(10, 1)).toBe(0);
  });

  it("uses a truecolor sweep on 24-bit terminals and static fallback elsewhere", () => {
    expect(resolveActiveStatusStyle(false, 24)).toEqual({ color: "#7fe7ff", bold: true });
    expect(resolveActiveStatusStyle(true, 24)).toEqual({ color: "#ff8cf6", bold: true });
    expect(resolveActiveStatusStyle(false, 256)).toEqual({ color: "cyan", bold: false });
    expect(resolveActiveStatusStyle(true, 16)).toEqual({ color: "magenta", bold: false });

    expect(resolveActiveLabelStyles("Read", 1, false, 24)).toEqual([
      { char: "R", color: "#4dcfff", bold: true, dimColor: false, inverse: false },
      { char: "e", color: "#7fe7ff", bold: true, dimColor: false, inverse: true },
      { char: "a", color: "#4dcfff", bold: true, dimColor: false, inverse: false },
      { char: "d", color: "#2f9bff", bold: false, dimColor: false, inverse: false },
    ]);

    expect(resolveActiveLabelStyles("Go", 0, true, 256)).toEqual([
      { char: "G", color: "magenta", bold: false, dimColor: false, inverse: false },
      { char: "o", color: "magenta", bold: false, dimColor: false, inverse: false },
    ]);
  });

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

  it("shows complexity while thinking when present", () => {
    const stream: ActiveStream = {
      runId: "r1",
      content: "",
      tools: [],
      isThinking: true,
      startedAt: Date.now(),
      complexity: {
        score: 42,
        level: "medium",
        version: "openfang-v1",
      },
    };
    const { lastFrame } = render(<ActiveStreamView stream={stream} />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("Complexity C42 medium");
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

  it("shows delegation target and task for delegate tools", () => {
    const stream: ActiveStream = {
      runId: "r1",
      content: "",
      tools: [
        {
          name: "delegate",
          callId: "c2",
          arguments: {
            agent_name: "researcher",
            task: "deep research on openfang vs openclaw and key differentiators",
          },
          status: "running",
        },
      ],
      isThinking: false,
      startedAt: Date.now(),
    };
    const { lastFrame } = render(<ActiveStreamView stream={stream} />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("delegate");
    expect(frame).toContain("researcher");
    expect(frame).toContain("openfang vs openclaw");
  });

  it("shows skill name for use_skill tools", () => {
    const stream: ActiveStream = {
      runId: "r1",
      content: "",
      tools: [
        {
          name: "use_skill",
          callId: "c3",
          arguments: { name: "agent-evaluation" },
          status: "running",
        },
      ],
      isThinking: false,
      startedAt: Date.now(),
    };
    const { lastFrame } = render(<ActiveStreamView stream={stream} />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("use_skill -> agent-evaluation");
  });

  it("returns null when stream is null", () => {
    const { lastFrame } = render(<ActiveStreamView stream={null} />);
    expect(lastFrame()).toBe("");
  });
});

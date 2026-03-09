import { describe, expect, it } from "vitest";
import { render } from "ink-testing-library";

import { ConversationView } from "../ConversationView.js";
import type { OutputBlock } from "../../types/blocks.js";

describe("ConversationView", () => {
  it("renders completed blocks only", () => {
    const completedBlocks: OutputBlock[] = [
      {
        id: "text-1",
        type: "text",
        content: "assistant output",
        timestamp: Date.now(),
      },
    ];

    const { lastFrame } = render(
      <ConversationView completedBlocks={completedBlocks} width={80} />,
    );

    expect(lastFrame() ?? "").toContain("assistant output");
  });

  it("does not render blank spacer lines between conversation blocks", () => {
    const completedBlocks: OutputBlock[] = [
      {
        id: "user-1",
        type: "user",
        content: "hey there",
        timestamp: Date.now(),
      },
      {
        id: "text-1",
        type: "text",
        content: "Hello! How can I help you today?",
        timestamp: Date.now(),
      },
    ];

    const { lastFrame } = render(
      <ConversationView completedBlocks={completedBlocks} width={80} />,
    );

    const frame = lastFrame() ?? "";
    const nonEmptyLines = frame
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    expect(nonEmptyLines[0]).toBe("> hey there");
    expect(nonEmptyLines[1]).toBe("Hello! How can I help you today?");
  });
});

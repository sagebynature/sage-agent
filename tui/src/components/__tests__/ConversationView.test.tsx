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
});

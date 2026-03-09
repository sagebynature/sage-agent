import { Box, Static } from "ink";
import { memo, type ReactNode } from "react";
import type { OutputBlock } from "../types/blocks.js";
import { StaticBlock } from "./blocks/StaticBlock.js";

interface ConversationViewProps {
  completedBlocks: OutputBlock[];
  width?: number;
}

export const ConversationView = memo(function ConversationView({
  completedBlocks,
  width,
}: ConversationViewProps): ReactNode {
  return (
    <Box flexDirection="column" width={width} paddingX={1}>
      <Static items={completedBlocks}>
        {(block) => <StaticBlock key={block.id} block={block} />}
      </Static>
    </Box>
  );
});

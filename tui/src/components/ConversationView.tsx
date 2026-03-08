import { Box, Static } from "ink";
import type { ReactNode } from "react";
import type { OutputBlock, ActiveStream } from "../types/blocks.js";
import { StaticBlock } from "./blocks/StaticBlock.js";
import { ActiveStreamView } from "./ActiveStreamView.js";

interface ConversationViewProps {
  completedBlocks: OutputBlock[];
  activeStream: ActiveStream | null;
  width?: number;
}

export function ConversationView({
  completedBlocks,
  activeStream,
  width,
}: ConversationViewProps): ReactNode {
  return (
    <Box flexDirection="column" width={width} paddingX={1}>
      <Static items={completedBlocks}>
        {(block) => (
          <Box key={block.id} flexDirection="column">
            <StaticBlock block={block} />
          </Box>
        )}
      </Static>
      <ActiveStreamView stream={activeStream} />
    </Box>
  );
}

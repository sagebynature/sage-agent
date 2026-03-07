import { Box, Static } from "ink";
import type { ReactNode } from "react";
import type { OutputBlock, ActiveStream } from "../types/blocks.js";
import { StaticBlock } from "./blocks/StaticBlock.js";
import { ActiveStreamView } from "./ActiveStreamView.js";

interface ConversationViewProps {
  completedBlocks: OutputBlock[];
  activeStream: ActiveStream | null;
}

export function ConversationView({
  completedBlocks,
  activeStream,
}: ConversationViewProps): ReactNode {
  return (
    <Box flexDirection="column">
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

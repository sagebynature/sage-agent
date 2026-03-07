import { Box, Text } from "ink";
import type { ReactNode } from "react";
import type { OutputBlock } from "../../types/blocks.js";
import { UserBlock } from "./UserBlock.js";
import { TextBlock } from "./TextBlock.js";
import { ToolBlock } from "./ToolBlock.js";

interface StaticBlockProps {
  block: OutputBlock;
}

export function StaticBlock({ block }: StaticBlockProps): ReactNode {
  switch (block.type) {
    case "user":
      return <UserBlock content={block.content} />;
    case "text":
      return <TextBlock content={block.content} />;
    case "tool":
      return <ToolBlock name={block.content} tools={block.tools ?? []} />;
    case "error":
      return (
        <Box>
          <Text color="red">{"● "}{block.content}</Text>
        </Box>
      );
    case "system":
      return (
        <Box>
          <Text dimColor italic>{"● "}{block.content}</Text>
        </Box>
      );
    default:
      return null;
  }
}

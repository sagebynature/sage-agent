import { Box, Text } from "ink";
import type { ReactNode } from "react";
import { renderMarkdown } from "../../renderer/MarkdownRenderer.js";

interface TextBlockProps {
  content: string;
}

export function TextBlock({ content }: TextBlockProps): ReactNode {
  const rendered = renderMarkdown(content, false);
  return (
    <Box flexDirection="column">
      <Text>{"● "}{rendered}</Text>
    </Box>
  );
}

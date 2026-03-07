import { Box, Text } from "ink";
import type { ReactNode } from "react";

interface UserBlockProps {
  content: string;
}

export function UserBlock({ content }: UserBlockProps): ReactNode {
  return (
    <Box>
      <Text dimColor>{"> "}{content}</Text>
    </Box>
  );
}

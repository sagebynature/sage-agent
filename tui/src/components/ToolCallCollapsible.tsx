import { Box, Text, useInput, useFocus } from 'ink';
import { useState } from 'react';
import type { ReactNode } from 'react';

interface ToolCallCollapsibleProps {
  title: ReactNode;
  children: ReactNode;
  defaultExpanded?: boolean;
  isFailed?: boolean;
}

export const ToolCallCollapsible = ({
  title,
  children,
  defaultExpanded = false,
  isFailed = false
}: ToolCallCollapsibleProps) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded || isFailed);
  const { isFocused } = useFocus();

  useInput((_input, key) => {
    if (isFocused && key.return) {
      setIsExpanded(prev => !prev);
    }
  });

  return (
    <Box flexDirection="column">
      <Box>
        <Text color={isFocused ? "blue" : undefined}>
          {isExpanded ? "▼ " : "▶ "}
        </Text>
        {title}
      </Box>
      {isExpanded && (
        <Box paddingLeft={1} flexDirection="column">
          {children}
        </Box>
      )}
    </Box>
  );
};

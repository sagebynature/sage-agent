import React from 'react';
import { Box, Text } from 'ink';

export interface TokenUsageBarProps {
  prompt: number;
  completion: number;
  max: number;
}

export const TokenUsageBar: React.FC<TokenUsageBarProps> = ({ prompt, completion, max }) => {
  const total = prompt + completion;
  const percentage = Math.min(100, Math.round((total / max) * 100));

  const width = 40;
  const promptWidth = Math.floor((prompt / max) * width);
  const completionWidth = Math.floor((completion / max) * width);
  const remainingWidth = Math.max(0, width - promptWidth - completionWidth);

  return (
    <Box flexDirection="column">
      <Box>
        <Text color="blue">{'█'.repeat(promptWidth)}</Text>
        <Text color="green">{'█'.repeat(completionWidth)}</Text>
        <Text color="gray">{'░'.repeat(remainingWidth)}</Text>
      </Box>
      <Text dimColor>
        {total} / {max} tokens ({percentage}%)
      </Text>
    </Box>
  );
};

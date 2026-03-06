import React from 'react';
import { Box, Text } from 'ink';

interface DiffBarProps {
  additions: number;
  deletions: number;
  width?: number; // Total width in characters for the bar visualization
}

export const DiffBar: React.FC<DiffBarProps> = ({ additions, deletions, width = 20 }) => {
  const total = additions + deletions;

  if (total === 0) {
    return <Text color="gray">No changes</Text>;
  }

  const addRatio = additions / total;
  const delRatio = deletions / total;

  let addChars = Math.round(addRatio * width);
  let delChars = Math.round(delRatio * width);

  if (additions > 0 && addChars === 0) addChars = 1;
  if (deletions > 0 && delChars === 0) delChars = 1;

  if (addChars + delChars > width) {
    if (addChars > delChars) addChars = width - delChars;
    else delChars = width - addChars;
  }

  const addBar = '█'.repeat(addChars);
  const delBar = '█'.repeat(delChars);

  return (
    <Box flexDirection="row" gap={1}>
      <Text>
        <Text color="green">+{additions}</Text>
        <Text> / </Text>
        <Text color="red">-{deletions}</Text>
      </Text>
      <Text>
        <Text color="green">{addBar}</Text>
        <Text color="red">{delBar}</Text>
      </Text>
    </Box>
  );
};

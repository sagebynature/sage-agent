import React from "react";
import { Box, Text } from "ink";
import { COLORS } from "../../theme/colors.js";

export const TasksTab: React.FC = () => {
  return (
    <Box padding={1}>
      <Text color={COLORS.dimmed}>No background tasks</Text>
    </Box>
  );
};

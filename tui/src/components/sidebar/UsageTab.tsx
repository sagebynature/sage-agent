import React from "react";
import { Box, Text } from "ink";
import { useApp } from "../../state/AppContext.js";
import { TokenUsageBar } from "../TokenUsageBar.js";
import { COLORS } from "../../theme/colors.js";

export const UsageTab: React.FC = () => {
  const { state } = useApp();
  const { usage } = state;
  const { promptTokens, completionTokens, totalCost, contextUsagePercent } = usage;

  const totalTokens = promptTokens + completionTokens;
  // Calculate max tokens based on percentage if available, otherwise default to total + 1000
  const maxTokens =
    contextUsagePercent > 0
      ? Math.round(totalTokens / (contextUsagePercent / 100))
      : totalTokens > 0
      ? totalTokens * 1.5 // Rough estimate if percentage is 0
      : 8192; // Default fallback

  return (
    <Box flexDirection="column" gap={1} padding={1}>
      <Box flexDirection="column">
        <Text color={COLORS.dimmed}>Total Cost</Text>
        <Text color={COLORS.accent}>${totalCost.toFixed(4)}</Text>
      </Box>

      <Box flexDirection="column" marginTop={1}>
        <Text color={COLORS.dimmed}>Context Usage</Text>
        <TokenUsageBar
          prompt={promptTokens}
          completion={completionTokens}
          max={maxTokens}
        />
      </Box>
    </Box>
  );
};

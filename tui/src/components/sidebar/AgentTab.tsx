import React from "react";
import { Box, Text } from "ink";
import { useApp } from "../../state/AppContext.js";
import { COLORS } from "../../theme/colors.js";

export const AgentTab: React.FC = () => {
  const { state } = useApp();
  const { agents, usage } = state;

  if (agents.length === 0) {
    return (
      <Box padding={1}>
        <Text color={COLORS.dimmed}>No agents running</Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column" gap={1} padding={1}>
      <Box flexDirection="column">
        <Text color={COLORS.dimmed}>Model</Text>
        <Text color={COLORS.accent}>{usage.model || "Unknown"}</Text>
      </Box>

      <Box flexDirection="column" gap={1}>
        <Text color={COLORS.dimmed}>Agents</Text>
        {agents.map((agent) => (
          <Box key={agent.name} flexDirection="column" borderStyle="single" borderColor={COLORS.dimmed} paddingX={1}>
            <Box justifyContent="space-between">
              <Text bold color={COLORS.brand}>{agent.name}</Text>
              <Text color={agent.status === "active" ? COLORS.streaming : COLORS.idle}>
                {agent.status}
              </Text>
            </Box>
            {agent.task && (
              <Box marginTop={1}>
                <Text>{agent.task}</Text>
              </Box>
            )}
          </Box>
        ))}
      </Box>
    </Box>
  );
};

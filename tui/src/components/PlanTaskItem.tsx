import { Box, Text } from "ink";
import { type PlanTask } from "../contexts/PlanContext.js";

interface PlanTaskItemProps {
  task: PlanTask;
  index: number;
  isActive: boolean;
}

export function PlanTaskItem({ task, isActive }: PlanTaskItemProps) {
  let symbol = "○";
  let color = "dim";

  switch (task.status) {
    case "completed":
      symbol = "✓";
      color = "green";
      break;
    case "running":
      symbol = "▶";
      color = "cyan";
      break;
    case "failed":
      symbol = "✗";
      color = "red";
      break;
    case "pending":
    default:
      symbol = "○";
      color = "dim";
      break;
  }

  return (
    <Box>
      <Box marginRight={1}>
        <Text color={color}>{symbol}</Text>
      </Box>
      <Box>
        <Text
          color={isActive ? "cyan" : undefined}
          wrap="truncate-end"
        >
          {task.description}
        </Text>
      </Box>
    </Box>
  );
}

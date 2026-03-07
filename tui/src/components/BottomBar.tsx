import { Box, Text } from "ink";
import type { ReactNode } from "react";
import type { UsageState } from "../types/state.js";

interface BottomBarProps {
  usage: UsageState;
}

function contextBar(percent: number): string {
  const filled = Math.round(percent / 10);
  const empty = 10 - filled;
  return "█".repeat(filled) + "░".repeat(empty);
}

function contextColor(percent: number): string {
  if (percent >= 90) return "red";
  if (percent >= 70) return "yellow";
  return "green";
}

export function BottomBar({ usage }: BottomBarProps): ReactNode {
  const cost = usage.totalCost > 0 ? `$${usage.totalCost.toFixed(2)}` : "";
  const model = usage.model || "no model";
  const pct = usage.contextUsagePercent;

  return (
    <Box>
      <Text dimColor>
        {"  "}{model}
        {" | "}
        <Text color={contextColor(pct)}>{contextBar(pct)}</Text>
        {" "}{pct}%
        {cost ? ` | ${cost}` : ""}
      </Text>
    </Box>
  );
}

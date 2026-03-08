import { Box, Text } from "ink";
import React, { type ReactNode } from "react";
import type { ToolSummary } from "../types/blocks.js";
import { formatToolLabel, formatToolResultPreview } from "../utils/tool-format.js";

interface ToolDisplayProps {
  tools: ToolSummary[];
}

function formatDuration(ms?: number): string {
  if (ms === undefined) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function ToolStatusLine({ tool }: { tool: ToolSummary }): ReactNode {
  const label = formatToolLabel(tool.name, tool.arguments);
  const duration = formatDuration(tool.durationMs);
  const preview = formatToolResultPreview(tool);

  if (tool.status === "failed") {
    return (
      <Box flexDirection="column">
        <Text>
          <Text color="red">{"  ✗ "}{label}</Text>
          <Text dimColor>{"  "}{tool.error ?? "failed"}</Text>
        </Text>
        {preview && <Text dimColor>{"    -> "}{preview}</Text>}
      </Box>
    );
  }

  return (
    <Box flexDirection="column">
      <Text dimColor>
        {"  ✓ "}{label}{duration ? `  ${duration}` : ""}
      </Text>
      {preview && <Text dimColor>{"    -> "}{preview}</Text>}
    </Box>
  );
}

function ToolDisplayComponent({ tools }: ToolDisplayProps): ReactNode {
  if (tools.length === 0) return null;

  const primary = tools[0]!;
  const primaryLabel = formatToolLabel(primary.name, primary.arguments);
  const duration = formatDuration(primary.durationMs);
  const isFailed = primary.status === "failed";
  const preview = tools.length === 1 ? formatToolResultPreview(primary) : null;

  const summary =
    tools.length === 1
      ? `${primaryLabel}${isFailed ? ` ✗ ${primary.error ?? "failed"}` : duration ? `  ${duration}` : ""}`
      : tools.every((t) => t.name === primary.name)
        ? `${primary.name} (${tools.length} calls)`
        : `${tools.length} tool calls`;

  const icon = isFailed ? "✗" : "●";
  const iconColor = isFailed ? "red" : undefined;

  return (
    <Box flexDirection="column">
      <Text>
        <Text color={iconColor}>{icon} </Text>
        {summary}
      </Text>
      {preview && <Text dimColor>{"  -> "}{preview}</Text>}
      {tools.length > 1 &&
        tools.map((tool, idx) => (
          <ToolStatusLine key={`${idx}_${tool.callId}`} tool={tool} />
        ))}
    </Box>
  );
}

export const ToolDisplay = React.memo(ToolDisplayComponent);

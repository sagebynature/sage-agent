import { Box, Text } from "ink";
import React, { type ReactNode } from "react";
import type { ToolSummary } from "../types/blocks.js";

interface ToolDisplayProps {
  tools: ToolSummary[];
}

function formatDuration(ms?: number): string {
  if (ms === undefined) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatToolArgs(tool: ToolSummary): string {
  const args = tool.arguments;
  if (args.path) return ` ${args.path}`;
  if (args.file_path) return ` ${args.file_path}`;
  if (args.command) return ` ${args.command}`;
  if (args.pattern) return ` ${args.pattern}`;
  if (args.url) return ` ${args.url}`;
  return "";
}

function ToolStatusLine({ tool }: { tool: ToolSummary }): ReactNode {
  const args = formatToolArgs(tool);
  const duration = formatDuration(tool.durationMs);

  if (tool.status === "failed") {
    return (
      <Text>
        <Text color="red">{"  ✗ "}{tool.name}</Text>
        <Text dimColor>{args}{"  "}{tool.error ?? "failed"}</Text>
      </Text>
    );
  }

  return (
    <Text dimColor>
      {"  ✓ "}{tool.name}{args}{duration ? `  ${duration}` : ""}
    </Text>
  );
}

function ToolDisplayComponent({ tools }: ToolDisplayProps): ReactNode {
  if (tools.length === 0) return null;

  const primary = tools[0]!;
  const args = formatToolArgs(primary);
  const duration = formatDuration(primary.durationMs);
  const isFailed = primary.status === "failed";

  const summary =
    tools.length === 1
      ? `${primary.name}${args}${isFailed ? ` ✗ ${primary.error ?? "failed"}` : duration ? `  ${duration}` : ""}`
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
      {tools.length > 1 &&
        tools.map((tool, idx) => (
          <ToolStatusLine key={`${idx}_${tool.callId}`} tool={tool} />
        ))}
    </Box>
  );
}

export const ToolDisplay = React.memo(ToolDisplayComponent);

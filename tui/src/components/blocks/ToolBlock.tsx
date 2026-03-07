import { Box, Text } from "ink";
import type { ReactNode } from "react";
import type { ToolSummary } from "../../types/blocks.js";

interface ToolBlockProps {
  name: string;
  tools: ToolSummary[];
}

function formatDuration(ms?: number): string {
  if (ms === undefined) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function toolStatusSuffix(tool: ToolSummary): string {
  if (tool.status === "running") return "... running";
  if (tool.status === "failed") return `✗ ${tool.error ?? "failed"}`;
  return formatDuration(tool.durationMs);
}

function toolSummaryLine(tools: ToolSummary[]): string {
  if (tools.length === 0) return "";
  if (tools.length === 1) {
    const t = tools[0]!;
    const suffix = toolStatusSuffix(t);
    const args = formatToolArgs(t);
    return `${t.name}${args}${suffix ? `  ${suffix}` : ""}`;
  }
  const name = tools[0]!.name;
  const allSame = tools.every((t) => t.name === name);
  if (allSame) {
    return `${name} (${tools.length} calls)`;
  }
  return `${tools.length} tool calls`;
}

function formatToolArgs(tool: ToolSummary): string {
  const args = tool.arguments;
  if (args.path) return ` ${args.path}`;
  if (args.file_path) return ` ${args.file_path}`;
  if (args.command) return ` ${args.command}`;
  return "";
}

export function ToolBlock({ tools }: ToolBlockProps): ReactNode {
  const summary = toolSummaryLine(tools);
  const subItems = tools.length > 1 ? tools : [];

  return (
    <Box flexDirection="column">
      <Text>{"● "}{summary}</Text>
      {subItems.map((tool) => (
        <Text key={tool.callId} dimColor>
          {"  ⎿  "}{tool.name}{formatToolArgs(tool)}
          {"  "}{toolStatusSuffix(tool)}
        </Text>
      ))}
    </Box>
  );
}

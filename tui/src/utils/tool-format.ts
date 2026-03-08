import type { ToolSummary } from "../types/blocks.js";

type ToolLike = Pick<ToolSummary, "name" | "result" | "error">;

function compact(value: unknown, max = 72): string {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  if (!text) return "";
  return text.length > max ? `${text.slice(0, max - 3)}...` : text;
}

function quoted(value: unknown, max = 72): string {
  const text = compact(value, max);
  return text ? `"${text}"` : "";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? value as Record<string, unknown> : null;
}

function summarizeArgs(args: Record<string, unknown>): string[] {
  const entries = Object.entries(args)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .slice(0, 2)
    .map(([key, value]) => `${key}=${compact(value, 32)}`);
  return entries;
}

export function formatToolLabel(name: string, args: Record<string, unknown>): string {
  const agentTarget = typeof args.agent_name === "string"
    ? args.agent_name
    : typeof args.agentName === "string"
      ? args.agentName
      : typeof args.target === "string"
        ? args.target
        : undefined;

  if (agentTarget) {
    const task = args.task ?? args.input;
    const sessionId = typeof args.session_id === "string"
      ? args.session_id
      : typeof args.sessionId === "string"
        ? args.sessionId
        : undefined;
    return `${name} -> ${agentTarget}${task ? ` ${quoted(task)}` : ""}${sessionId ? ` [session ${sessionId}]` : ""}`;
  }

  const skillName = typeof args.name === "string"
    ? args.name
    : typeof args.skill_name === "string"
      ? args.skill_name
      : typeof args.skillName === "string"
        ? args.skillName
        : undefined;
  if (name === "use_skill" && skillName) {
    return `${name} -> ${skillName}`;
  }

  const nestedArgs = asRecord(args.arguments);
  const toolName = typeof args.tool_name === "string"
    ? args.tool_name
    : typeof args.toolName === "string"
      ? args.toolName
      : undefined;
  if (toolName && nestedArgs) {
    return `${name} -> ${formatToolLabel(toolName, nestedArgs)}`;
  }

  if (args.path) return `${name} ${compact(args.path)}`;
  if (args.file_path) return `${name} ${compact(args.file_path)}`;
  if (args.command) return `${name} ${quoted(args.command, 84)}`;
  if (args.pattern) return `${name} ${quoted(args.pattern)}`;
  if (args.url) return `${name} ${compact(args.url)}`;
  if (args.q) return `${name} ${quoted(args.q)}`;
  if (args.query) return `${name} ${quoted(args.query)}`;
  if (args.task) return `${name} ${quoted(args.task)}`;

  const argsSummary = summarizeArgs(args);
  return argsSummary.length > 0 ? `${name} ${argsSummary.join(" ")}` : name;
}

export function formatToolResultPreview(tool: ToolLike, max = 88): string | null {
  if (tool.error) {
    return compact(tool.error, max);
  }
  if (!tool.result) {
    return null;
  }

  const trimmed = tool.result.replace(/\s+/g, " ").trim();
  if (!trimmed) {
    return null;
  }

  if (tool.name === "use_skill") {
    const firstHeading = trimmed.match(/^#+\s+(.+)$/m)?.[1];
    if (firstHeading) {
      return `loaded ${compact(firstHeading, max - 7)}`;
    }
  }

  return compact(trimmed, max);
}

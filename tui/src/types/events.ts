export type EventCategory =
  | "run"
  | "llm"
  | "tool"
  | "memory"
  | "compaction"
  | "delegation"
  | "permission"
  | "background"
  | "session"
  | "coordination"
  | "planning"
  | "system";

export type EventPhase =
  | "start"
  | "delta"
  | "complete"
  | "fail"
  | "cancel"
  | "point";

export type EventStatus = "ok" | "error" | "cancelled" | "skipped";

export type VerbosityMode = "compact" | "normal" | "debug";

export interface UsageSnapshot {
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
  cacheReadTokens?: number;
  cacheCreationTokens?: number;
  reasoningTokens?: number;
  cost?: number;
}

export interface ErrorSnapshot {
  type: string;
  message: string;
  retryable?: boolean;
  providerCode?: string;
}

export interface EventRecord {
  id: string;
  eventName: string;
  category: EventCategory;
  phase: EventPhase;
  status?: EventStatus;
  timestamp: number;
  agentName: string;
  agentPath: string[];
  runId?: string;
  turnId?: string;
  turnIndex?: number;
  sessionId?: string;
  originatingSessionId?: string;
  parentEventId?: string;
  triggerEventId?: string;
  traceId?: string;
  spanId?: string;
  durationMs?: number;
  usage?: UsageSnapshot;
  payload: Record<string, unknown>;
  error?: ErrorSnapshot;
  sourceMethod?: string;
  summary: string;
}

export interface EventFilters {
  categories: EventCategory[];
  statuses: EventStatus[];
  search: string;
}

export interface RunSummary {
  runId: string;
  status: "running" | "completed" | "failed" | "cancelled";
  agentPath: string[];
  agentName: string;
  sessionId?: string;
  originatingSessionId?: string;
  startedAt: number;
  completedAt?: number;
  lastEventId?: string;
  turnIndex?: number;
}

const COMPACT_EVENT_NAMES = new Set([
  "on_run_started",
  "on_run_completed",
  "on_run_failed",
  "on_run_cancelled",
  "pre_tool_execute",
  "post_tool_execute",
  "on_tool_failed",
  "on_tool_skipped",
  "on_delegation",
  "on_delegation_complete",
  "on_delegation_failed",
  "background_task_completed",
  "background_task_failed",
  "background_task_cancelled",
  "permission_request",
  "permission_resolved",
]);

const NORMAL_EVENT_NAMES = new Set([
  ...COMPACT_EVENT_NAMES,
  "pre_llm_call",
  "post_llm_call",
  "on_llm_retry",
  "on_llm_error",
  "pre_compaction",
  "post_compaction",
  "compaction_failed",
  "pre_memory_recall",
  "post_memory_recall",
  "pre_memory_store",
  "post_memory_store",
  "pre_permission_check",
  "post_permission_check",
  "on_session_started",
  "on_session_resumed",
  "on_session_closed",
]);

function trimText(value: string, maxLength = 96): string {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 3)}...`;
}

function toNumber(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function complexityText(payload: Record<string, unknown>): string {
  const complexity = typeof payload.complexity === "object" && payload.complexity !== null
    ? payload.complexity as Record<string, unknown>
    : null;
  if (!complexity) {
    return "";
  }
  const score = toNumber(complexity.score);
  const level = typeof complexity.level === "string" ? complexity.level : undefined;
  if (score === undefined || !level) {
    return "";
  }
  return ` C${score} ${level}`;
}

function stringFromPayload(payload: Record<string, unknown>, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "string" && value.length > 0) {
      return value;
    }
  }
  return undefined;
}

export function formatEventSummary(event: EventRecord): string {
  const payload = event.payload;
  switch (event.eventName) {
    case "on_run_started":
      return `run started`;
    case "on_run_completed":
      return `run completed`;
    case "on_run_failed":
      return `run failed${event.error?.message ? `: ${trimText(event.error.message, 60)}` : ""}`;
    case "on_run_cancelled":
      return `run cancelled`;
    case "pre_llm_call":
      return `turn ${event.turnIndex ?? payload.turn ?? "?"} started${stringFromPayload(payload, "model") ? ` on ${stringFromPayload(payload, "model")}` : ""}${complexityText(payload)}`;
    case "post_llm_call":
      return `turn ${event.turnIndex ?? payload.turn ?? "?"} completed${complexityText(payload)}`;
    case "on_llm_retry":
      return `llm retry triggered`;
    case "on_llm_error":
      return `llm error${event.error?.message ? `: ${trimText(event.error.message, 60)}` : ""}`;
    case "on_llm_stream_delta":
      return `assistant streamed ${String(stringFromPayload(payload, "delta") ?? "").length} chars`;
    case "pre_tool_execute":
      return `tool ${stringFromPayload(payload, "tool_name", "toolName") ?? "unknown"} started`;
    case "post_tool_execute":
      return `tool ${stringFromPayload(payload, "tool_name", "toolName") ?? "unknown"} completed`;
    case "on_tool_failed":
      return `tool ${stringFromPayload(payload, "tool_name", "toolName") ?? "unknown"} failed`;
    case "on_tool_skipped":
      return `tool ${stringFromPayload(payload, "tool_name", "toolName") ?? "unknown"} skipped`;
    case "on_delegation":
      return `delegated to ${stringFromPayload(payload, "target", "agentName") ?? "agent"}`;
    case "on_delegation_complete":
      return `${stringFromPayload(payload, "target", "agentName") ?? "agent"} completed`;
    case "on_delegation_failed":
      return `${stringFromPayload(payload, "target", "agentName") ?? "agent"} failed`;
    case "background_task_completed":
      return `background task ${stringFromPayload(payload, "task_id", "taskId") ?? "unknown"} completed`;
    case "background_task_failed":
      return `background task ${stringFromPayload(payload, "task_id", "taskId") ?? "unknown"} failed`;
    case "background_task_cancelled":
      return `background task ${stringFromPayload(payload, "task_id", "taskId") ?? "unknown"} cancelled`;
    case "pre_memory_recall":
      return `memory recall started`;
    case "post_memory_recall": {
      const count = toNumber(payload.count);
      return count !== undefined ? `memory recall returned ${count} entries` : "memory recall completed";
    }
    case "pre_memory_store":
      return `memory store started`;
    case "post_memory_store":
      return `memory stored`;
    case "pre_compaction":
      return `compaction started`;
    case "post_compaction":
      return `compaction completed`;
    case "compaction_failed":
      return `compaction failed`;
    case "pre_permission_check":
      return `permission check started`;
    case "post_permission_check":
      return `permission check completed`;
    case "permission_request":
      return `permission requested for ${stringFromPayload(payload, "tool") ?? "tool"}`;
    case "permission_resolved":
      return `permission ${stringFromPayload(payload, "decision") ?? "resolved"}`;
    default:
      return event.eventName.replaceAll("_", " ");
  }
}

export function eventVisibleAtVerbosity(
  event: EventRecord,
  verbosity: VerbosityMode,
): boolean {
  if (verbosity === "debug") {
    return true;
  }
  if (verbosity === "normal") {
    return NORMAL_EVENT_NAMES.has(event.eventName);
  }
  return COMPACT_EVENT_NAMES.has(event.eventName);
}

export function eventMatchesFilters(event: EventRecord, filters: EventFilters): boolean {
  if (filters.categories.length > 0 && !filters.categories.includes(event.category)) {
    return false;
  }
  if (filters.statuses.length > 0) {
    if (!event.status || !filters.statuses.includes(event.status)) {
      return false;
    }
  }
  if (filters.search) {
    const haystack = [
      event.summary,
      event.eventName,
      event.agentName,
      event.agentPath.join(" "),
      JSON.stringify(event.payload),
      event.error?.message ?? "",
    ]
      .join(" ")
      .toLowerCase();
    if (!haystack.includes(filters.search.toLowerCase())) {
      return false;
    }
  }
  return true;
}

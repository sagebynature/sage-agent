import { METHODS } from "../types/protocol.js";
import {
  formatEventSummary,
  type ErrorSnapshot,
  type EventCategory,
  type EventPhase,
  type EventRecord,
  type EventStatus,
  type UsageSnapshot,
} from "../types/events.js";
import { makeId } from "../state/blockReducer.js";

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : {};
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string");
}

function normalizeUsage(value: unknown): UsageSnapshot | undefined {
  const usage = asRecord(value);
  if (Object.keys(usage).length === 0) {
    return undefined;
  }
  return {
    promptTokens: asNumber(usage.promptTokens) ?? asNumber(usage.input),
    completionTokens: asNumber(usage.completionTokens) ?? asNumber(usage.output),
    totalTokens: asNumber(usage.totalTokens),
    cacheReadTokens: asNumber(usage.cacheReadTokens),
    cacheCreationTokens: asNumber(usage.cacheCreationTokens),
    reasoningTokens: asNumber(usage.reasoningTokens),
    cost: asNumber(usage.cost),
  };
}

function normalizeError(value: unknown): ErrorSnapshot | undefined {
  const error = asRecord(value);
  const message = asString(error.message);
  if (!message) {
    return undefined;
  }
  return {
    type: asString(error.type) ?? "Error",
    message,
    retryable: error.retryable === true,
    providerCode: asString(error.providerCode),
  };
}

function normalizeEnvelope(params: Record<string, unknown>): EventRecord {
  const payload = asRecord(params.payload);
  const agentName = asString(params.agentName) ?? "agent";
  const agentPath = asStringArray(params.agentPath);
  const event: EventRecord = {
    id: asString(params.eventId) ?? makeId("event"),
    eventName: asString(params.eventName) ?? "unknown_event",
    category: (asString(params.category) ?? "system") as EventCategory,
    phase: (asString(params.phase) ?? "point") as EventPhase,
    status: asString(params.status) as EventStatus | undefined,
    timestamp: asNumber(params.timestamp) ?? Date.now(),
    agentName,
    agentPath: agentPath.length > 0 ? agentPath : [agentName],
    runId: asString(params.runId),
    turnId: asString(params.turnId),
    turnIndex: asNumber(params.turnIndex),
    sessionId: asString(params.sessionId),
    originatingSessionId: asString(params.originatingSessionId),
    parentEventId: asString(params.parentEventId),
    triggerEventId: asString(params.triggerEventId),
    traceId: asString(params.traceId),
    spanId: asString(params.spanId),
    durationMs: asNumber(params.durationMs),
    usage: normalizeUsage(params.usage),
    payload,
    error: normalizeError(params.error),
    sourceMethod: METHODS.EVENT_EMITTED,
    summary: "",
  };
  event.summary = formatEventSummary(event);
  return event;
}

function legacyEvent(
  method: string,
  params: Record<string, unknown>,
  defaults: {
    eventName: string;
    category: EventCategory;
    phase: EventPhase;
    status?: EventStatus;
  },
): EventRecord {
  const agentPath = asStringArray(params.agent_path).length > 0
    ? asStringArray(params.agent_path)
    : asStringArray(params.agentPath);
  const agentName =
    asString(params.agentName) ??
    asString(params.target) ??
    agentPath.at(-1) ??
    "agent";
  const event: EventRecord = {
    id: makeId("event"),
    eventName: defaults.eventName,
    category: defaults.category,
    phase: defaults.phase,
    status: defaults.status,
    timestamp: Date.now(),
    agentName,
    agentPath: agentPath.length > 0 ? agentPath : [agentName],
    runId: asString(params.runId),
    turnId: asString(params.turnId),
    turnIndex: asNumber(params.turnIndex) ?? asNumber(params.turn),
    sessionId: asString(params.sessionId),
    originatingSessionId: asString(params.originatingSessionId),
    parentEventId: undefined,
    triggerEventId: undefined,
    traceId: undefined,
    spanId: undefined,
    durationMs: asNumber(params.durationMs) ?? asNumber(params.duration),
    usage: normalizeUsage(params.usage),
    payload: params,
    error: normalizeError(params.error) ?? (asString(params.message)
      ? {
          type: "Error",
          message: asString(params.message) ?? "Unknown error",
          retryable: false,
        }
      : undefined),
    sourceMethod: method,
    summary: "",
  };
  event.summary = formatEventSummary(event);
  return event;
}

export class EventNormalizer {
  normalizeNotification(
    method: string,
    params: Record<string, unknown>,
  ): EventRecord | null {
    switch (method) {
      case METHODS.EVENT_EMITTED:
        return normalizeEnvelope(params as unknown as Record<string, unknown>);

      case METHODS.STREAM_DELTA:
        return legacyEvent(method, params, {
          eventName: "on_llm_stream_delta",
          category: "llm",
          phase: "delta",
        });

      case METHODS.TOOL_STARTED:
        return legacyEvent(method, params, {
          eventName: "pre_tool_execute",
          category: "tool",
          phase: "start",
        });

      case METHODS.TOOL_COMPLETED:
        return legacyEvent(method, params, {
          eventName: asString(params.error) ? "on_tool_failed" : "post_tool_execute",
          category: "tool",
          phase: asString(params.error) ? "fail" : "complete",
          status: asString(params.error) ? "error" : "ok",
        });

      case METHODS.RUN_COMPLETED: {
        const status = asString(params.status);
        return legacyEvent(method, params, {
          eventName:
            status === "cancelled"
              ? "on_run_cancelled"
              : status === "error"
                ? "on_run_failed"
                : "on_run_completed",
          category: "run",
          phase:
            status === "cancelled" ? "cancel" : status === "error" ? "fail" : "complete",
          status:
            status === "cancelled" ? "cancelled" : status === "error" ? "error" : "ok",
        });
      }

      case METHODS.DELEGATION_STARTED:
        return legacyEvent(method, params, {
          eventName: "on_delegation",
          category: "delegation",
          phase: "start",
        });

      case METHODS.DELEGATION_COMPLETED:
        return legacyEvent(method, params, {
          eventName: asString(params.error)
            ? "on_delegation_failed"
            : "on_delegation_complete",
          category: "delegation",
          phase: asString(params.error) ? "fail" : "complete",
          status: asString(params.error) ? "error" : "ok",
        });

      case METHODS.BACKGROUND_COMPLETED: {
        const status = asString(params.status);
        return legacyEvent(method, params, {
          eventName:
            status === "failed"
              ? "background_task_failed"
              : status === "cancelled"
                ? "background_task_cancelled"
                : "background_task_completed",
          category: "background",
          phase:
            status === "failed"
              ? "fail"
              : status === "cancelled"
                ? "cancel"
                : "complete",
          status:
            status === "failed"
              ? "error"
              : status === "cancelled"
                ? "cancelled"
                : "ok",
        });
      }

      case METHODS.PERMISSION_REQUEST:
        return legacyEvent(method, params, {
          eventName: "permission_request",
          category: "permission",
          phase: "point",
        });

      case METHODS.COMPACTION_STARTED:
        return legacyEvent(method, params, {
          eventName: "pre_compaction",
          category: "compaction",
          phase: "start",
        });

      case METHODS.ERROR:
        return legacyEvent(method, params, {
          eventName: "system_error",
          category: "system",
          phase: "fail",
          status: "error",
        });

      case METHODS.TURN_STARTED:
      case METHODS.LLM_TURN_STARTED:
        return legacyEvent(method, params, {
          eventName: "pre_llm_call",
          category: "llm",
          phase: "start",
        });

      case METHODS.TURN_COMPLETED:
      case METHODS.LLM_TURN_COMPLETED:
        return legacyEvent(method, params, {
          eventName: "post_llm_call",
          category: "llm",
          phase: "complete",
          status: "ok",
        });

      default:
        return null;
    }
  }
}

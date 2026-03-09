import type { BlockAction } from "../state/blockReducer.js";
import type { EventRecord } from "../types/events.js";
import type { PermissionState } from "../types/state.js";
import { makeId } from "../state/blockReducer.js";
import type { ComplexitySummary } from "../types/blocks.js";

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asComplexity(value: unknown): ComplexitySummary | null {
  const record = asRecord(value);
  const score = typeof record.score === "number" ? record.score : undefined;
  const level = record.level;
  if (
    score === undefined
    || (level !== "simple" && level !== "medium" && level !== "complex")
  ) {
    return null;
  }
  return {
    score,
    level,
    version: typeof record.version === "string" ? record.version : undefined,
  };
}

function agentParentName(agentPath: string[]): string | undefined {
  return agentPath.length > 1 ? agentPath[agentPath.length - 2] : undefined;
}

export class EventProjector {
  private readonly pendingCalls = new Map<string, string[]>();

  project(event: EventRecord): BlockAction[] {
    const payload = event.payload;
    switch (event.eventName) {
      case "on_run_started":
        return event.runId ? [{ type: "STREAM_START", runId: event.runId }] : [];

      case "on_llm_stream_delta": {
        const delta = asString(payload.delta);
        return delta ? [{ type: "STREAM_DELTA", delta }] : [];
      }

      case "pre_llm_call": {
        const complexity = asComplexity(payload.complexity);
        return complexity ? [{ type: "SET_ACTIVE_COMPLEXITY", complexity }] : [];
      }

      case "pre_tool_execute": {
        const toolName = asString(payload.tool_name) ?? asString(payload.toolName) ?? "tool";
        const explicitCallId = asString(payload.tool_call_id) ?? asString(payload.toolCallId) ?? asString(payload.callId);
        const callId = explicitCallId ?? makeId("toolcall");
        if (!explicitCallId) {
          const pending = this.pendingCalls.get(toolName) ?? [];
          pending.push(callId);
          this.pendingCalls.set(toolName, pending);
        }
        return [{
          type: "TOOL_STARTED",
          name: toolName,
          callId,
          arguments: asRecord(payload.arguments),
        }];
      }

      case "post_tool_execute":
      case "on_tool_failed":
      case "on_tool_skipped": {
        const toolName = asString(payload.tool_name) ?? asString(payload.toolName) ?? "tool";
        const explicitCallId = asString(payload.tool_call_id) ?? asString(payload.toolCallId) ?? asString(payload.callId);
        let callId = explicitCallId;
        if (!callId) {
          const pending = this.pendingCalls.get(toolName);
          if (pending && pending.length > 0) {
            callId = pending.shift()!;
          } else {
            callId = `call_0_${toolName}`;
          }
        }
        if (!callId) {
          return [];
        }
        return [{
          type: "TOOL_COMPLETED",
          callId,
          result: asString(payload.result),
          error: event.error?.message ?? asString(payload.error),
          durationMs: event.durationMs,
        }];
      }

      case "on_run_completed":
        return [{ type: "STREAM_END", status: "success" }];

      case "on_run_failed":
        return [{
          type: "STREAM_END",
          status: "error",
          error: event.error?.message ?? asString(payload.error),
        }];

      case "on_run_cancelled":
        return [{ type: "STREAM_END", status: "cancelled" }];

      case "permission_request": {
        const permission: PermissionState = {
          id: asString(payload.requestId) ?? asString(payload.request_id) ?? makeId("perm"),
          tool: asString(payload.tool) ?? "tool",
          arguments: asRecord(payload.arguments),
          command: asString(payload.command),
          riskLevel:
            payload.riskLevel === "low" || payload.riskLevel === "medium" || payload.riskLevel === "high"
              ? payload.riskLevel
              : "medium",
          status: "pending",
        };
        return [{ type: "PERMISSION_REQUEST", permission }];
      }

      case "system_error":
        return [{
          type: "SET_ERROR",
          error: event.error?.message ?? asString(payload.message) ?? "Unknown error",
        }];

      case "pre_compaction":
        return [{
          type: "ADD_SYSTEM_BLOCK",
          content: `Context compaction started${asString(payload.reason) ? `: ${asString(payload.reason)}` : ""}`,
        }];

      case "background_task_completed":
      case "background_task_failed":
      case "background_task_cancelled": {
        const taskId = asString(payload.task_id) ?? asString(payload.taskId) ?? "task";
        const status = asString(payload.status)
          ?? (event.eventName === "background_task_failed"
            ? "failed"
            : event.eventName === "background_task_cancelled"
              ? "cancelled"
              : "completed");
        return [{
          type: "ADD_SYSTEM_BLOCK",
          content: `Background task ${taskId} ${status}`,
        }];
      }

      case "on_delegation": {
        const target = asString(payload.target) ?? asString(payload.agentName) ?? event.agentPath.at(-1) ?? "subagent";
        const task = asString(payload.task) ?? asString(payload.input) ?? "";
        const delegationId = asString(payload.delegation_id) ?? asString(payload.delegationId) ?? target;
        return [
          {
            type: "AGENT_STARTED",
            agent: {
              name: target,
              status: "active",
              parentName: agentParentName(event.agentPath),
              task,
              depth: Math.max(1, event.agentPath.length - 1),
              children: [],
              startedAt: event.timestamp,
              agentPath: event.agentPath,
              runId: event.runId,
              sessionId: event.sessionId,
              delegationId,
            },
          }
        ];
      }

      case "on_delegation_complete":
      case "on_delegation_failed": {
        const target = asString(payload.target) ?? asString(payload.agentName) ?? event.agentPath.at(-1) ?? "subagent";
        const delegationId = asString(payload.delegation_id) ?? asString(payload.delegationId) ?? target;
        return [
          {
            type: "AGENT_COMPLETED",
            name: target,
            status: event.eventName === "on_delegation_failed" ? "failed" : "completed",
            delegationId,
            agentPath: event.agentPath,
          },
          {
            type: "ADD_SYSTEM_BLOCK",
            content: `Subagent ${target} ${event.eventName === "on_delegation_failed" ? "failed" : "completed"}`,
          },
        ];
      }

      default:
        return [];
    }
  }
}

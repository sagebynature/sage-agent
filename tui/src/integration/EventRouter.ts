import type { AppAction } from "../state/AppContext.js";
import {
  METHODS,
  type BackgroundCompletedPayload,
  type CompactionStartedPayload,
  type DelegationCompletedPayload,
  type DelegationStartedPayload,
  type ErrorPayload,
  type RunCompletedPayload,
  type PermissionRequestPayload,
  type StreamDeltaPayload,
  type ToolCompletedPayload,
  type ToolStartedPayload,
  type UsageUpdatePayload,
} from "../types/protocol.js";

type Dispatch = (action: AppAction) => void;

export class EventRouter {
  private readonly dispatch: Dispatch;
  private currentTurn: number | null = null;
  private currentMessageId: string | null = null;
  private accumulatedContent = "";
  private batchTimer: ReturnType<typeof setTimeout> | null = null;
  private batchedContent = "";
  private readonly BATCH_WINDOW_MS = 16;

  constructor(dispatch: Dispatch) {
    this.dispatch = dispatch;
  }

  handleNotification(method: string, params: Record<string, unknown>): void {
    try {
      switch (method) {
        case METHODS.STREAM_DELTA:
          this.handleStreamDelta(this.parseStreamDelta(params));
          return;
        case METHODS.TOOL_STARTED:
          this.handleToolStarted(this.parseToolStarted(params));
          return;
        case METHODS.TOOL_COMPLETED:
          this.handleToolCompleted(this.parseToolCompleted(params));
          return;
        case METHODS.DELEGATION_STARTED:
          this.handleDelegationStarted(this.parseDelegationStarted(params));
          return;
        case METHODS.DELEGATION_COMPLETED:
          this.handleDelegationCompleted(this.parseDelegationCompleted(params));
          return;
        case METHODS.BACKGROUND_COMPLETED:
          this.handleBackgroundCompleted(this.parseBackgroundCompleted(params));
          return;
        case METHODS.PERMISSION_REQUEST:
          this.handlePermissionRequest(this.parsePermissionRequest(params));
          return;
        case METHODS.USAGE_UPDATE:
          this.handleUsageUpdate(this.parseUsageUpdate(params));
          return;
        case METHODS.COMPACTION_STARTED:
          this.handleCompactionStarted(this.parseCompactionStarted(params));
          return;
        case METHODS.ERROR:
          this.handleError(this.parseError(params));
          return;
        case METHODS.RUN_COMPLETED:
          this.handleRunCompleted(this.parseRunCompleted(params));
          return;
        default:
          console.warn(`Unknown notification method: ${method}`, params);
      }
    } catch (error) {
      const raw = this.safeStringify({ method, params });
      this.handleParseError(
        raw,
        error instanceof Error ? error : new Error(String(error)),
      );
    }
  }

  private handleStreamDelta(params: StreamDeltaPayload): void {
    const turn = typeof params.turn === "number" ? params.turn : 0;
    const delta = typeof params.delta === "string" ? params.delta : "";

    const isNewTurn = this.currentTurn !== turn;
    if (isNewTurn) {
      this.flushBatch();
      this.currentTurn = turn;
      this.currentMessageId = `assistant-${turn}-${Date.now()}`;
      this.accumulatedContent = delta;

      this.dispatch({
        type: "ADD_MESSAGE",
        message: {
          id: this.currentMessageId,
          role: "assistant",
          content: this.accumulatedContent,
          timestamp: Date.now(),
          isStreaming: true,
        },
      });
      this.dispatch({ type: "SET_STREAMING", isStreaming: true });
      return;
    }

    if (!this.currentMessageId) {
      return;
    }

    this.batchedContent += delta;
    if (!this.batchTimer) {
      this.batchTimer = setTimeout(() => {
        this.flushBatch();
      }, this.BATCH_WINDOW_MS);
    }
  }

  dispose(): void {
    this.flushBatch();
  }

  private flushBatch(): void {
    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
      this.batchTimer = null;
    }

    if (!this.currentMessageId || this.batchedContent.length === 0) {
      return;
    }

    this.accumulatedContent += this.batchedContent;
    this.batchedContent = "";
    this.dispatch({
      type: "UPDATE_MESSAGE",
      id: this.currentMessageId,
      updates: {
        content: this.accumulatedContent,
      },
    });
  }

  private handleToolStarted(params: ToolStartedPayload): void {
    this.dispatch({
      type: "TOOL_STARTED",
      tool: {
        id: params.callId,
        name: params.toolName,
        status: "running",
        arguments: params.arguments,
        startedAt: Date.now(),
      },
    });
  }

  private handleToolCompleted(params: ToolCompletedPayload): void {
    const action: AppAction = {
      type: "TOOL_COMPLETED",
      id: params.callId,
    };

    if (typeof params.result === "string") {
      action.result = params.result;
    }
    if (typeof params.error === "string" && params.error.length > 0) {
      action.error = params.error;
    }

    this.dispatch(action);
  }

  private handleDelegationStarted(params: DelegationStartedPayload): void {
    // MCP discovery fan-out is serialized server-side, so rapid delegation
    // notifications are handled deterministically and do not race here.
    this.dispatch({
      type: "AGENT_STARTED",
      agent: {
        name: params.target,
        status: "active",
        task: params.task,
        depth: 1,
        children: [],
        startedAt: Date.now(),
      },
    });
  }

  private handleDelegationCompleted(params: DelegationCompletedPayload): void {
    this.dispatch({
      type: "AGENT_COMPLETED",
      name: params.target,
      status: "completed",
    });
  }

  private handleBackgroundCompleted(params: BackgroundCompletedPayload): void {
    const action: AppAction = {
      type: "BACKGROUND_TASK_UPDATE",
      taskId: params.taskId,
      status: params.status,
    };

    if (typeof params.result === "string") {
      action.result = params.result;
    }
    if (typeof params.error === "string") {
      action.error = params.error;
    }

    this.dispatch(action);
  }

  private handlePermissionRequest(params: PermissionRequestPayload): void {
    this.dispatch({
      type: "PERMISSION_REQUEST",
      permission: {
        id: params.requestId,
        tool: params.tool,
        arguments: params.arguments,
        command: params.command,
        riskLevel: params.riskLevel,
        status: "pending",
      },
    });
  }

  private handleUsageUpdate(params: UsageUpdatePayload): void {
    this.dispatch({
      type: "UPDATE_USAGE",
      usage: {
        promptTokens: params.promptTokens,
        completionTokens: params.completionTokens,
        totalCost: params.totalCost,
        model: params.model,
        contextUsagePercent: params.contextUsagePercent,
      },
    });
  }

  private handleCompactionStarted(params: CompactionStartedPayload): void {
    this.dispatch({
      type: "COMPACTION_STARTED",
      reason: params.reason,
    });
  }

  private handleRunCompleted(params: RunCompletedPayload): void {
    this.flushBatch();

    // Mark the last streaming message as complete
    if (this.currentMessageId) {
      this.dispatch({
        type: "UPDATE_MESSAGE",
        id: this.currentMessageId,
        updates: { isStreaming: false },
      });
    }

    // Reset stream tracking state
    this.currentTurn = null;
    this.currentMessageId = null;
    this.accumulatedContent = "";

    this.dispatch({ type: "SET_STREAMING", isStreaming: false });

    if (params.status === "error" && params.error) {
      this.dispatch({ type: "SET_ERROR", error: params.error });
    }
  }

  private handleError(params: ErrorPayload): void {
    this.dispatch({
      type: "SET_ERROR",
      error: params.message,
    });
  }

  private parseStreamDelta(params: Record<string, unknown>): StreamDeltaPayload {
    return {
      delta: this.asString(params.delta),
      turn: this.asNumber(params.turn),
    };
  }

  private parseToolStarted(params: Record<string, unknown>): ToolStartedPayload {
    return {
      toolName: this.asString(params.toolName),
      callId: this.asString(params.callId),
      arguments: this.asRecord(params.arguments),
    };
  }

  private parseToolCompleted(
    params: Record<string, unknown>,
  ): ToolCompletedPayload {
    return {
      toolName: this.asString(params.toolName),
      callId: this.asString(params.callId),
      result: this.asString(params.result),
      error: this.asOptionalString(params.error),
      durationMs: this.asNumber(params.durationMs),
    };
  }

  private parseDelegationStarted(
    params: Record<string, unknown>,
  ): DelegationStartedPayload {
    return {
      target: this.asString(params.target),
      task: this.asString(params.task),
    };
  }

  private parseDelegationCompleted(
    params: Record<string, unknown>,
  ): DelegationCompletedPayload {
    return {
      target: this.asString(params.target),
      result: this.asString(params.result),
    };
  }

  private parseBackgroundCompleted(
    params: Record<string, unknown>,
  ): BackgroundCompletedPayload {
    return {
      taskId: this.asString(params.taskId),
      agentName: this.asString(params.agentName),
      status: this.asString(params.status),
      result: this.asOptionalString(params.result),
      error: this.asOptionalString(params.error),
    };
  }

  private parsePermissionRequest(
    params: Record<string, unknown>,
  ): PermissionRequestPayload {
    const riskLevel = params.riskLevel;
    return {
      requestId: this.asString(params.requestId),
      tool: this.asString(params.tool),
      arguments: this.asRecord(params.arguments),
      command: this.asOptionalString(params.command),
      riskLevel:
        riskLevel === "low" || riskLevel === "medium" || riskLevel === "high"
          ? riskLevel
          : "medium",
    };
  }

  private parseUsageUpdate(params: Record<string, unknown>): UsageUpdatePayload {
    return {
      promptTokens: this.asNumber(params.promptTokens),
      completionTokens: this.asNumber(params.completionTokens),
      totalCost: this.asNumber(params.totalCost),
      model: this.asString(params.model),
      contextUsagePercent: this.asNumber(params.contextUsagePercent),
    };
  }

  private parseCompactionStarted(
    params: Record<string, unknown>,
  ): CompactionStartedPayload {
    return {
      reason: this.asString(params.reason),
      beforeTokens: this.asNumber(params.beforeTokens),
    };
  }

  private parseRunCompleted(params: Record<string, unknown>): RunCompletedPayload {
    const status = params.status;
    return {
      runId: this.asString(params.runId),
      status:
        status === "success" || status === "error" || status === "cancelled"
          ? status
          : "error",
      error: this.asOptionalString(params.error),
    };
  }

  private parseError(params: Record<string, unknown>): ErrorPayload {
    return {
      code: this.asString(params.code),
      message: this.asString(params.message),
      recoverable: this.asBoolean(params.recoverable),
    };
  }

  private asString(value: unknown): string {
    return typeof value === "string" ? value : "";
  }

  private asOptionalString(value: unknown): string | undefined {
    return typeof value === "string" ? value : undefined;
  }

  private asNumber(value: unknown): number {
    return typeof value === "number" ? value : 0;
  }

  private asBoolean(value: unknown): boolean {
    return typeof value === "boolean" ? value : false;
  }

  private asRecord(value: unknown): Record<string, unknown> {
    if (typeof value === "object" && value !== null) {
      return value as Record<string, unknown>;
    }

    return {};
  }

  private handleParseError(raw: string, error: Error): void {
    console.error("Failed to parse notification payload", { raw, error });
  }

  private safeStringify(value: unknown): string {
    try {
      return JSON.stringify(value);
    } catch {
      return "<unserializable notification payload>";
    }
  }
}

export function createEventRouter(dispatch: Dispatch): EventRouter {
  return new EventRouter(dispatch);
}

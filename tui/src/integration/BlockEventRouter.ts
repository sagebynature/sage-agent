import { METHODS } from "../types/protocol.js";
import type { BlockAction } from "../state/blockReducer.js";

type Dispatch = (action: BlockAction) => void;

export class BlockEventRouter {
  private readonly dispatch: Dispatch;

  constructor(dispatch: Dispatch) {
    this.dispatch = dispatch;
  }

  handleNotification(method: string, params: Record<string, unknown>): void {
    switch (method) {
      case METHODS.STREAM_DELTA:
        this.dispatch({
          type: "STREAM_DELTA",
          delta: typeof params.delta === "string" ? params.delta : "",
        });
        return;

      case METHODS.TOOL_STARTED:
        this.dispatch({
          type: "TOOL_STARTED",
          name: typeof params.toolName === "string" ? params.toolName : "",
          callId: typeof params.callId === "string" ? params.callId : "",
          arguments: typeof params.arguments === "object" && params.arguments !== null
            ? (params.arguments as Record<string, unknown>)
            : {},
        });
        return;

      case METHODS.TOOL_COMPLETED:
        this.dispatch({
          type: "TOOL_COMPLETED",
          callId: typeof params.callId === "string" ? params.callId : "",
          result: typeof params.result === "string" ? params.result : undefined,
          error: typeof params.error === "string" && params.error.length > 0 ? params.error : undefined,
          durationMs: typeof params.durationMs === "number" ? params.durationMs : undefined,
        });
        return;

      case METHODS.RUN_COMPLETED: {
        const status = params.status;
        this.dispatch({
          type: "STREAM_END",
          status:
            status === "success" || status === "error" || status === "cancelled"
              ? status
              : "error",
          error: typeof params.error === "string" ? params.error : undefined,
        });
        return;
      }

      case METHODS.USAGE_UPDATE:
        this.dispatch({
          type: "UPDATE_USAGE",
          usage: {
            promptTokens: typeof params.promptTokens === "number" ? params.promptTokens : 0,
            completionTokens: typeof params.completionTokens === "number" ? params.completionTokens : 0,
            totalCost: typeof params.totalCost === "number" ? params.totalCost : 0,
            model: typeof params.model === "string" ? params.model : "",
            contextUsagePercent: typeof params.contextUsagePercent === "number" ? params.contextUsagePercent : 0,
          },
        });
        return;

      case METHODS.PERMISSION_REQUEST:
        this.dispatch({
          type: "PERMISSION_REQUEST",
          permission: {
            id: typeof params.requestId === "string" ? params.requestId : "",
            tool: typeof params.tool === "string" ? params.tool : "",
            arguments: typeof params.arguments === "object" && params.arguments !== null
              ? (params.arguments as Record<string, unknown>)
              : {},
            riskLevel:
              params.riskLevel === "low" || params.riskLevel === "medium" || params.riskLevel === "high"
                ? params.riskLevel
                : "medium",
            status: "pending",
          },
        });
        return;

      case METHODS.ERROR:
        this.dispatch({
          type: "SET_ERROR",
          error: typeof params.message === "string" ? params.message : "Unknown error",
        });
        return;

      case METHODS.COMPACTION_STARTED:
        this.dispatch({
          type: "ADD_SYSTEM_BLOCK",
          content: `Context compaction started: ${typeof params.reason === "string" ? params.reason : "unknown"}`,
        });
        return;

      case METHODS.BACKGROUND_COMPLETED:
        this.dispatch({
          type: "ADD_SYSTEM_BLOCK",
          content: `Background task ${typeof params.taskId === "string" ? params.taskId : ""} ${typeof params.status === "string" ? params.status : "completed"}`,
        });
        return;

      default:
        return;
    }
  }
}

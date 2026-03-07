import type {
  OutputBlock,
  ActiveStream,
  ToolSummary,
} from "../types/blocks.js";
import type {
  UsageState,
  PermissionState,
  PermissionDecision,
  SessionState,
} from "../types/state.js";

export interface BlockState {
  completedBlocks: OutputBlock[];
  activeStream: ActiveStream | null;
  usage: UsageState;
  permissions: PermissionState[];
  error: string | null;
  session: SessionState | null;
}

export type BlockAction =
  | { type: "SUBMIT_MESSAGE"; content: string }
  | { type: "STREAM_START"; runId: string }
  | { type: "STREAM_DELTA"; delta: string }
  | {
      type: "TOOL_STARTED";
      name: string;
      callId: string;
      arguments: Record<string, unknown>;
    }
  | {
      type: "TOOL_COMPLETED";
      callId: string;
      result?: string;
      error?: string;
      durationMs?: number;
    }
  | {
      type: "STREAM_END";
      status: "success" | "error" | "cancelled";
      error?: string;
    }
  | { type: "UPDATE_USAGE"; usage: Partial<UsageState> }
  | { type: "SET_ERROR"; error: string }
  | { type: "CLEAR_ERROR" }
  | { type: "PERMISSION_REQUEST"; permission: PermissionState }
  | { type: "PERMISSION_RESPOND"; id: string; decision: PermissionDecision }
  | { type: "SET_SESSION"; session: SessionState | null }
  | { type: "ADD_SYSTEM_BLOCK"; content: string };

export const INITIAL_BLOCK_STATE: BlockState = {
  completedBlocks: [],
  activeStream: null,
  usage: {
    promptTokens: 0,
    completionTokens: 0,
    totalCost: 0,
    model: "",
    contextUsagePercent: 0,
  },
  permissions: [],
  error: null,
  session: null,
};

export function makeId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function resolvePermissionStatus(
  decision: PermissionDecision,
): "approved" | "denied" {
  return decision === "deny" ? "denied" : "approved";
}

function flattenStream(
  stream: ActiveStream,
  endStatus: "success" | "error" | "cancelled",
): OutputBlock[] {
  const blocks: OutputBlock[] = [];
  const now = Date.now();
  for (const tool of stream.tools) {
    const resolvedTool: ToolSummary =
      tool.status === "running"
        ? {
            ...tool,
            status: endStatus === "cancelled" ? "failed" : "completed",
            error: endStatus === "cancelled" ? "cancelled" : tool.error,
            durationMs: now - stream.startedAt,
          }
        : tool;
    blocks.push({
      id: makeId("tool"),
      type: "tool",
      content: resolvedTool.name,
      tools: [resolvedTool],
      timestamp: now,
    });
  }
  const text = stream.content.trim();
  if (text.length > 0) {
    blocks.push({
      id: makeId("text"),
      type: "text",
      content: text,
      timestamp: now,
    });
  }
  return blocks;
}

export function blockReducer(
  state: BlockState,
  action: BlockAction,
): BlockState {
  switch (action.type) {
    case "SUBMIT_MESSAGE": {
      const block: OutputBlock = {
        id: makeId("user"),
        type: "user",
        content: action.content,
        timestamp: Date.now(),
      };
      return {
        ...state,
        completedBlocks: [...state.completedBlocks, block],
      };
    }

    case "STREAM_START": {
      return {
        ...state,
        activeStream: {
          runId: action.runId,
          content: "",
          tools: [],
          isThinking: true,
          startedAt: Date.now(),
        },
      };
    }

    case "STREAM_DELTA": {
      const stream = state.activeStream ?? {
        runId: `auto_${Date.now()}`,
        content: "",
        tools: [],
        isThinking: true,
        startedAt: Date.now(),
      };
      return {
        ...state,
        activeStream: {
          ...stream,
          content: stream.content + action.delta,
          isThinking: false,
        },
      };
    }

    case "TOOL_STARTED": {
      const stream = state.activeStream ?? {
        runId: `auto_${Date.now()}`,
        content: "",
        tools: [],
        isThinking: true,
        startedAt: Date.now(),
      };
      const tool: ToolSummary = {
        name: action.name,
        callId: action.callId,
        arguments: action.arguments,
        status: "running",
      };
      return {
        ...state,
        activeStream: {
          ...stream,
          tools: [...stream.tools, tool],
        },
      };
    }

    case "TOOL_COMPLETED": {
      if (!state.activeStream) return state;
      return {
        ...state,
        activeStream: {
          ...state.activeStream,
          tools: state.activeStream.tools.map((t) =>
            t.callId === action.callId
              ? {
                  ...t,
                  result: action.result,
                  error: action.error,
                  durationMs: action.durationMs,
                  status: (action.error ? "failed" : "completed") as
                    | "completed"
                    | "failed",
                }
              : t,
          ),
        },
      };
    }

    case "STREAM_END": {
      const newBlocks: OutputBlock[] = [];
      if (state.activeStream) {
        newBlocks.push(...flattenStream(state.activeStream, action.status));
      }
      if (action.status === "error" && action.error) {
        newBlocks.push({
          id: makeId("error"),
          type: "error",
          content: action.error,
          timestamp: Date.now(),
        });
      }
      return {
        ...state,
        completedBlocks: [...state.completedBlocks, ...newBlocks],
        activeStream: null,
      };
    }

    case "UPDATE_USAGE": {
      return {
        ...state,
        usage: { ...state.usage, ...action.usage },
      };
    }

    case "SET_ERROR": {
      return { ...state, error: action.error };
    }

    case "CLEAR_ERROR": {
      return { ...state, error: null };
    }

    case "PERMISSION_REQUEST": {
      return {
        ...state,
        permissions: [...state.permissions, action.permission],
      };
    }

    case "PERMISSION_RESPOND": {
      return {
        ...state,
        permissions: state.permissions.map((p) =>
          p.id === action.id
            ? { ...p, status: resolvePermissionStatus(action.decision) }
            : p,
        ),
      };
    }

    case "SET_SESSION": {
      return { ...state, session: action.session };
    }

    case "ADD_SYSTEM_BLOCK": {
      const block: OutputBlock = {
        id: makeId("system"),
        type: "system",
        content: action.content,
        timestamp: Date.now(),
      };
      return {
        ...state,
        completedBlocks: [...state.completedBlocks, block],
      };
    }

    default:
      return state;
  }
}

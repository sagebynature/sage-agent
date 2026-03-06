import { createContext, use, useReducer, type ReactNode } from "react";
import type {
  AppState,
  ChatMessage,
  ToolCallState,
  PermissionState,
  SessionState,
  UsageState,
  AgentNode,
  PermissionDecision,
  ViewMode,
  AgentStatus,
} from "../types/state.js";

export const INITIAL_STATE: AppState = {
  currentView: "focused",
  messages: [],
  tools: [],
  permissions: [],
  session: null,
  agents: [],
  usage: {
    promptTokens: 0,
    completionTokens: 0,
    totalCost: 0,
    model: "",
    contextUsagePercent: 0,
  },
  isStreaming: false,
  error: null,
};

export type AppAction =
  | { type: "ADD_MESSAGE"; message: ChatMessage }
  | { type: "UPDATE_MESSAGE"; id: string; updates: Partial<ChatMessage> }
  | { type: "SET_STREAMING"; isStreaming: boolean }
  | { type: "TOOL_STARTED"; tool: ToolCallState }
  | { type: "TOOL_COMPLETED"; id: string; result?: string; error?: string }
  | { type: "PERMISSION_REQUEST"; permission: PermissionState }
  | { type: "PERMISSION_RESPOND"; id: string; decision: PermissionDecision }
  | { type: "SET_SESSION"; session: SessionState | null }
  | { type: "UPDATE_USAGE"; usage: Partial<UsageState> }
  | { type: "SET_ERROR"; error: string }
  | { type: "CLEAR_ERROR" }
  | { type: "SET_VIEW"; view: ViewMode }
  | { type: "AGENT_STARTED"; agent: AgentNode }
  | { type: "AGENT_COMPLETED"; name: string; status: "completed" | "failed" }
  | {
      type: "BACKGROUND_TASK_UPDATE";
      taskId: string;
      status: string;
      result?: string;
      error?: string;
    }
  | { type: "COMPACTION_STARTED"; reason: string };

function resolvePermissionStatus(
  decision: PermissionDecision,
): "approved" | "denied" {
  if (decision === "deny") return "denied";
  return "approved";
}

export function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "ADD_MESSAGE":
      return { ...state, messages: [...state.messages, action.message] };

    case "UPDATE_MESSAGE":
      return {
        ...state,
        messages: state.messages.map((msg) =>
          msg.id === action.id ? { ...msg, ...action.updates } : msg,
        ),
      };

    case "SET_STREAMING":
      return { ...state, isStreaming: action.isStreaming };

    case "TOOL_STARTED":
      return { ...state, tools: [...state.tools, action.tool] };

    case "TOOL_COMPLETED":
      return {
        ...state,
        tools: state.tools.map((tool) =>
          tool.id === action.id
            ? {
                ...tool,
                status: action.error ? ("failed" as const) : ("completed" as const),
                result: action.result,
                error: action.error,
                completedAt: Date.now(),
              }
            : tool,
        ),
      };

    case "PERMISSION_REQUEST":
      return {
        ...state,
        permissions: [...state.permissions, action.permission],
      };

    case "PERMISSION_RESPOND":
      return {
        ...state,
        permissions: state.permissions.map((perm) =>
          perm.id === action.id
            ? {
                ...perm,
                status: resolvePermissionStatus(action.decision),
              }
            : perm,
        ),
      };

    case "SET_SESSION":
      return { ...state, session: action.session };

    case "UPDATE_USAGE":
      return { ...state, usage: { ...state.usage, ...action.usage } };

    case "SET_ERROR":
      return { ...state, error: action.error };

    case "CLEAR_ERROR":
      return { ...state, error: null };

    case "SET_VIEW":
      return { ...state, currentView: action.view };

    case "AGENT_STARTED":
      return { ...state, agents: [...state.agents, action.agent] };

    case "AGENT_COMPLETED": {
      const completedStatus: AgentStatus = action.status;
      return {
        ...state,
        agents: state.agents.map((agent) =>
          agent.name === action.name
            ? { ...agent, status: completedStatus, completedAt: Date.now() }
            : agent,
        ),
      };
    }

    case "BACKGROUND_TASK_UPDATE": {
      const content = action.error
        ? `Background task ${action.taskId} failed: ${action.error}`
        : `Background task ${action.taskId} ${action.status}${action.result ? `: ${action.result}` : ""}`;
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: `bg_${action.taskId}_${Date.now()}`,
            role: "system" as const,
            content,
            timestamp: Date.now(),
            isStreaming: false,
          },
        ],
      };
    }

    case "COMPACTION_STARTED": {
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: `compaction_${Date.now()}`,
            role: "system" as const,
            content: `Context compaction started: ${action.reason}`,
            timestamp: Date.now(),
            isStreaming: false,
          },
        ],
      };
    }

    default:
      return state;
  }
}

const AppContext = createContext<{
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
} | null>(null);

export function AppProvider({
  children,
}: {
  children: ReactNode;
}): ReactNode {
  const [state, dispatch] = useReducer(appReducer, INITIAL_STATE);
  return <AppContext value={{ state, dispatch }}>{children}</AppContext>;
}

export function useApp() {
  const context = use(AppContext);
  if (!context) throw new Error("useApp must be used within AppProvider");
  return context;
}

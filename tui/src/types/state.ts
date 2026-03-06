export type ViewMode = "focused" | "split" | "dashboard";

export type ToolStatus = "pending" | "running" | "completed" | "failed";

export type PermissionDecision =
  | "allow_once"
  | "allow_always"
  | "allow_session"
  | "deny"
  | "edit";

export type PermissionStatus = "pending" | "approved" | "denied";

export type AgentStatus = "idle" | "active" | "completed" | "failed";

export interface ChatMessage {
  id: string;
  role: "system" | "user" | "assistant" | "tool";
  content: string | null;
  timestamp: number;
  toolCalls?: ToolCallState[];
  isStreaming: boolean;
}

export interface ToolCallState {
  id: string;
  name: string;
  status: ToolStatus;
  arguments: Record<string, unknown>;
  result?: string;
  error?: string;
  startedAt?: number;
  completedAt?: number;
}

export interface PermissionState {
  id: string;
  tool: string;
  arguments: Record<string, unknown>;
  command?: string;
  riskLevel: "low" | "medium" | "high";
  status: PermissionStatus;
}

export interface SessionState {
  id: string;
  agentName: string;
  createdAt: string;
  messageCount: number;
  model?: string;
  totalCost?: number;
  lastMessage?: string;
}

export interface AgentNode {
  name: string;
  status: AgentStatus;
  parentName?: string;
  task?: string;
  depth: number;
  children: AgentNode[];
  startedAt?: number;
  completedAt?: number;
}

export interface UsageState {
  promptTokens: number;
  completionTokens: number;
  totalCost: number;
  model: string;
  contextUsagePercent: number;
}

export interface AppState {
  currentView: ViewMode;
  messages: ChatMessage[];
  tools: ToolCallState[];
  permissions: PermissionState[];
  session: SessionState | null;
  agents: AgentNode[];
  usage: UsageState;
  isStreaming: boolean;
  error: string | null;
}

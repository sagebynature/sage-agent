// JSON-RPC 2.0 base types
export interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: number | string;
  method: string;
  params?: Record<string, unknown>;
}

export interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: number | string;
  result?: unknown;
  error?: JsonRpcError;
}

export interface JsonRpcNotification {
  jsonrpc: "2.0";
  method: string;
  params?: Record<string, unknown>;
}

export interface JsonRpcError {
  code: number;
  message: string;
  data?: unknown;
}

// Request param types
export interface AgentRunParams {
  message: string;
  sessionId?: string;
}

export interface AgentCancelParams {
  reason?: string;
}

export interface SessionListParams {
  agentName?: string;
}

export interface SessionResumeParams {
  sessionId: string;
}

export interface SessionClearParams {
  sessionId: string;
}

export interface ConfigGetParams {
  key: string;
}

export interface ConfigSetParams {
  key: string;
  value: unknown;
}

export interface ToolsListParams {}

export interface PermissionRespondParams {
  requestId: string;
  decision: "allow_once" | "allow_always" | "allow_session" | "deny" | "edit";
  editedCommand?: string;
}

// Response types
export interface AgentRunResult {
  status: "started";
  runId: string;
}

export interface SessionListResult {
  sessions: SessionInfo[];
}

export interface SessionInfo {
  id: string;
  agentName: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
  model?: string;
  totalCost?: number;
  firstMessage?: string;
}

export interface ConfigValue {
  key: string;
  value: unknown;
}

export interface ToolInfo {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

// Notification payloads
export interface StreamDeltaPayload {
  delta: string;
  turn: number;
}

export interface ToolStartedPayload {
  toolName: string;
  callId: string;
  arguments: Record<string, unknown>;
}

export interface ToolCompletedPayload {
  toolName: string;
  callId: string;
  result: string;
  error?: string;
  durationMs: number;
}

export interface DelegationStartedPayload {
  target: string;
  task: string;
}

export interface DelegationCompletedPayload {
  target: string;
  result: string;
}

export interface BackgroundCompletedPayload {
  taskId: string;
  agentName: string;
  status: string;
  result?: string;
  error?: string;
}

export interface PermissionRequestPayload {
  requestId: string;
  tool: string;
  arguments: Record<string, unknown>;
  command?: string;
  riskLevel: "low" | "medium" | "high";
}

export interface UsageUpdatePayload {
  promptTokens: number;
  completionTokens: number;
  totalCost: number;
  model: string;
  contextUsagePercent: number;
}

export interface CompactionStartedPayload {
  reason: string;
  beforeTokens: number;
}

export interface ErrorPayload {
  code: string;
  message: string;
  recoverable: boolean;
}

export interface RunCompletedPayload {
  runId: string;
  status: "success" | "error" | "cancelled";
  error?: string;
}

// Method name constants
export const METHODS = {
  INITIALIZE: "initialize",
  AGENT_RUN: "agent/run",
  AGENT_CANCEL: "agent/cancel",
  SESSION_LIST: "session/list",
  SESSION_RESUME: "session/resume",
  SESSION_CLEAR: "session/clear",
  CONFIG_GET: "config/get",
  CONFIG_SET: "config/set",
  TOOLS_LIST: "tools/list",
  PERMISSION_RESPOND: "permission/respond",
  // Notification methods (server -> client)
  STREAM_DELTA: "stream/delta",
  TOOL_STARTED: "tool/started",
  TOOL_COMPLETED: "tool/completed",
  DELEGATION_STARTED: "delegation/started",
  DELEGATION_COMPLETED: "delegation/completed",
  BACKGROUND_COMPLETED: "background/completed",
  PERMISSION_REQUEST: "permission/request",
  USAGE_UPDATE: "usage/update",
  COMPACTION_STARTED: "compaction/started",
  ERROR: "error",
  RUN_COMPLETED: "run/completed",
} as const;

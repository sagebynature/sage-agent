export interface StreamDeltaEvent {
  type: "stream_delta";
  delta: string;
  turn: number;
}

export interface ToolStartedEvent {
  type: "tool_started";
  name: string;
  callId: string;
  arguments: Record<string, unknown>;
}

export interface ToolCompletedEvent {
  type: "tool_completed";
  name: string;
  callId: string;
  result: string;
  error?: string;
  durationMs: number;
}

export interface LLMTurnStartedEvent {
  type: "llm_turn_started";
  turn: number;
  model: string;
  messageCount: number;
}

export interface LLMTurnCompletedEvent {
  type: "llm_turn_completed";
  turn: number;
  promptTokens: number;
  completionTokens: number;
  cost: number;
  toolCallCount: number;
}

export interface DelegationStartedEvent {
  type: "delegation_started";
  target: string;
  task: string;
}

export interface DelegationCompletedEvent {
  type: "delegation_completed";
  target: string;
  result: string;
}

export interface BackgroundCompletedEvent {
  type: "background_completed";
  taskId: string;
  agentName: string;
  status: string;
  result?: string;
  error?: string;
}

export interface PermissionRequestEvent {
  type: "permission_request";
  requestId: string;
  tool: string;
  arguments: Record<string, unknown>;
  command?: string;
  riskLevel: "low" | "medium" | "high";
}

export interface UsageUpdateEvent {
  type: "usage_update";
  promptTokens: number;
  completionTokens: number;
  totalCost: number;
  model: string;
  contextUsagePercent: number;
}

export interface CompactionEvent {
  type: "compaction_started";
  reason: string;
  beforeTokens: number;
}

export interface ErrorEvent {
  type: "error";
  code: string;
  message: string;
  recoverable: boolean;
}

export type SageEvent =
  | StreamDeltaEvent
  | ToolStartedEvent
  | ToolCompletedEvent
  | LLMTurnStartedEvent
  | LLMTurnCompletedEvent
  | DelegationStartedEvent
  | DelegationCompletedEvent
  | BackgroundCompletedEvent
  | PermissionRequestEvent
  | UsageUpdateEvent
  | CompactionEvent
  | ErrorEvent;

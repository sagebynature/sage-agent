import type {
  AppState,
  ChatMessage,
  ToolCallState,
  PermissionState,
  AgentNode,
} from "../types/state.js";

export function selectCurrentMessages(state: AppState): ChatMessage[] {
  return state.messages;
}

export function selectActiveTools(state: AppState): ToolCallState[] {
  return state.tools.filter((t) => t.status === "running");
}

export function selectPendingPermissions(state: AppState): PermissionState[] {
  return state.permissions.filter((p) => p.status === "pending");
}

export function selectAgentTree(state: AppState): AgentNode[] {
  return state.agents.filter((a) => !a.parentName);
}

export function selectTotalCost(state: AppState): string {
  return `$${state.usage.totalCost.toFixed(4)}`;
}

export function selectContextUsage(state: AppState): number {
  return state.usage.contextUsagePercent;
}

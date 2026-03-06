import { describe, it, expect } from "vitest";
import {
  selectCurrentMessages,
  selectActiveTools,
  selectPendingPermissions,
  selectAgentTree,
  selectTotalCost,
  selectContextUsage,
} from "../selectors.js";
import { INITIAL_STATE } from "../AppContext.js";
import type { AppState, ChatMessage, ToolCallState, PermissionState, AgentNode } from "../../types/state.js";

const makeMessage = (overrides: Partial<ChatMessage> = {}): ChatMessage => ({
  id: "msg-1",
  role: "user",
  content: "hello",
  timestamp: 1000,
  isStreaming: false,
  ...overrides,
});

const makeTool = (overrides: Partial<ToolCallState> = {}): ToolCallState => ({
  id: "tool-1",
  name: "shell",
  status: "running",
  arguments: {},
  ...overrides,
});

const makePermission = (
  overrides: Partial<PermissionState> = {},
): PermissionState => ({
  id: "perm-1",
  tool: "shell",
  arguments: {},
  riskLevel: "low",
  status: "pending",
  ...overrides,
});

const makeAgent = (overrides: Partial<AgentNode> = {}): AgentNode => ({
  name: "root-agent",
  status: "active",
  depth: 0,
  children: [],
  ...overrides,
});

describe("selectors", () => {
  it("selectCurrentMessages returns all messages", () => {
    const messages = [
      makeMessage({ id: "m1" }),
      makeMessage({ id: "m2", role: "assistant" }),
    ];
    const state: AppState = { ...INITIAL_STATE, messages };
    expect(selectCurrentMessages(state)).toBe(messages);
    expect(selectCurrentMessages(state)).toHaveLength(2);
  });

  it("selectActiveTools returns only running tools", () => {
    const tools = [
      makeTool({ id: "t1", status: "running" }),
      makeTool({ id: "t2", status: "completed" }),
      makeTool({ id: "t3", status: "running" }),
      makeTool({ id: "t4", status: "failed" }),
      makeTool({ id: "t5", status: "pending" }),
    ];
    const state: AppState = { ...INITIAL_STATE, tools };
    const active = selectActiveTools(state);
    expect(active).toHaveLength(2);
    expect(active.every((t) => t.status === "running")).toBe(true);
  });

  it("selectPendingPermissions returns only pending permissions", () => {
    const permissions = [
      makePermission({ id: "p1", status: "pending" }),
      makePermission({ id: "p2", status: "approved" }),
      makePermission({ id: "p3", status: "pending" }),
      makePermission({ id: "p4", status: "denied" }),
    ];
    const state: AppState = { ...INITIAL_STATE, permissions };
    const pending = selectPendingPermissions(state);
    expect(pending).toHaveLength(2);
    expect(pending.every((p) => p.status === "pending")).toBe(true);
  });

  it("selectAgentTree returns only root-level agents (no parentName)", () => {
    const agents: AgentNode[] = [
      makeAgent({ name: "root-1", depth: 0 }),
      makeAgent({ name: "child-1", parentName: "root-1", depth: 1 }),
      makeAgent({ name: "root-2", depth: 0 }),
      makeAgent({ name: "child-2", parentName: "root-2", depth: 1 }),
      makeAgent({ name: "grandchild", parentName: "child-1", depth: 2 }),
    ];
    const state: AppState = { ...INITIAL_STATE, agents };
    const tree = selectAgentTree(state);
    expect(tree).toHaveLength(2);
    expect(tree.every((a) => !a.parentName)).toBe(true);
    expect(tree.map((a) => a.name)).toEqual(["root-1", "root-2"]);
  });

  it("selectTotalCost formats cost as dollar string with 4 decimals", () => {
    const state: AppState = {
      ...INITIAL_STATE,
      usage: { ...INITIAL_STATE.usage, totalCost: 0.0123 },
    };
    expect(selectTotalCost(state)).toBe("$0.0123");
  });

  it("selectTotalCost formats zero cost correctly", () => {
    expect(selectTotalCost(INITIAL_STATE)).toBe("$0.0000");
  });

  it("selectContextUsage returns contextUsagePercent", () => {
    const state: AppState = {
      ...INITIAL_STATE,
      usage: { ...INITIAL_STATE.usage, contextUsagePercent: 75 },
    };
    expect(selectContextUsage(state)).toBe(75);
  });
});

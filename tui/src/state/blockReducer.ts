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
  AgentNode,
} from "../types/state.js";
import type {
  EventFilters,
  EventRecord,
  RunSummary,
  VerbosityMode,
} from "../types/events.js";
import { eventMatchesFilters, eventVisibleAtVerbosity } from "../types/events.js";

const MAX_EVENTS = 1000;

export interface BlockUiState {
  verbosity: VerbosityMode;
  showEventPane: boolean;
  selectedEventId: string | null;
  followEvents: boolean;
  filters: EventFilters;
}

export interface BlockState {
  completedBlocks: OutputBlock[];
  activeStream: ActiveStream | null;
  usage: UsageState;
  permissions: PermissionState[];
  error: string | null;
  session: SessionState | null;
  agents: AgentNode[];
  scrollOffset: number;
  events: EventRecord[];
  runs: Record<string, RunSummary>;
  ui: BlockUiState;
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
  | { type: "ADD_SYSTEM_BLOCK"; content: string }
  | { type: "EVENT_RECEIVED"; event: EventRecord }
  | { type: "SET_VERBOSITY"; verbosity: VerbosityMode }
  | { type: "TOGGLE_EVENT_PANE" }
  | { type: "SELECT_EVENT"; eventId: string | null }
  | { type: "SELECT_NEXT_EVENT" }
  | { type: "SELECT_PREV_EVENT" }
  | { type: "SET_EVENT_FOLLOW"; follow: boolean }
  | { type: "SET_EVENT_FILTERS"; filters: Partial<EventFilters> }
  | { type: "CLEAR_EVENT_FILTERS" }
  | { type: "AGENT_STARTED"; agent: AgentNode }
  | {
      type: "AGENT_COMPLETED";
      name: string;
      status: "completed" | "failed";
      delegationId?: string;
      agentPath?: string[];
    }
  | { type: "CLEAR_BLOCKS" }
  | { type: "SCROLL_UP"; lines?: number }
  | { type: "SCROLL_DOWN"; lines?: number }
  | { type: "SCROLL_TO_BOTTOM" };

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
  agents: [],
  scrollOffset: 0,
  events: [],
  runs: {},
  ui: {
    verbosity: "compact",
    showEventPane: false,
    selectedEventId: null,
    followEvents: true,
    filters: {
      categories: [],
      statuses: [],
      search: "",
    },
  },
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

function updateRuns(
  runs: Record<string, RunSummary>,
  event: EventRecord,
): Record<string, RunSummary> {
  if (!event.runId) {
    return runs;
  }

  const current = runs[event.runId] ?? {
    runId: event.runId,
    status: "running",
    agentPath: event.agentPath,
    agentName: event.agentName,
    sessionId: event.sessionId,
    originatingSessionId: event.originatingSessionId,
    startedAt: event.timestamp,
    turnIndex: event.turnIndex,
    lastEventId: event.id,
  };

  let status = current.status;
  let completedAt = current.completedAt;

  switch (event.eventName) {
    case "on_run_started":
      status = "running";
      break;
    case "on_run_completed":
      status = "completed";
      completedAt = event.timestamp;
      break;
    case "on_run_failed":
      status = "failed";
      completedAt = event.timestamp;
      break;
    case "on_run_cancelled":
      status = "cancelled";
      completedAt = event.timestamp;
      break;
    default:
      break;
  }

  return {
    ...runs,
    [event.runId]: {
      ...current,
      status,
      completedAt,
      agentPath: event.agentPath.length > 0 ? event.agentPath : current.agentPath,
      agentName: event.agentName || current.agentName,
      sessionId: event.sessionId ?? current.sessionId,
      originatingSessionId:
        event.originatingSessionId ?? current.originatingSessionId,
      turnIndex: event.turnIndex ?? current.turnIndex,
      lastEventId: event.id,
    },
  };
}

function upsertAgent(agents: AgentNode[], agent: AgentNode): AgentNode[] {
  const index = agents.findIndex((candidate) => {
    if (agent.delegationId && candidate.delegationId) {
      return candidate.delegationId === agent.delegationId;
    }
    if (
      agent.agentPath &&
      candidate.agentPath &&
      agent.agentPath.join("/") === candidate.agentPath.join("/")
    ) {
      return true;
    }
    return candidate.name === agent.name && candidate.parentName === agent.parentName;
  });

  if (index === -1) {
    return [...agents, agent];
  }

  const next = [...agents];
  next[index] = {
    ...next[index],
    ...agent,
    children: next[index]?.children ?? [],
  };
  return next;
}

function updateAgentStatus(
  agents: AgentNode[],
  action: Extract<BlockAction, { type: "AGENT_COMPLETED" }>,
): AgentNode[] {
  return agents.map((agent) => {
    const sameDelegation =
      action.delegationId && agent.delegationId === action.delegationId;
    const samePath =
      action.agentPath &&
      agent.agentPath &&
      action.agentPath.join("/") === agent.agentPath.join("/");
    const sameName = agent.name === action.name;

    if (!sameDelegation && !samePath && !sameName) {
      return agent;
    }

    return {
      ...agent,
      status: action.status,
      completedAt: Date.now(),
    };
  });
}

function cycleSelection(
  events: EventRecord[],
  selectedEventId: string | null,
  direction: 1 | -1,
): string | null {
  if (events.length === 0) {
    return null;
  }

  if (!selectedEventId) {
    return direction > 0 ? events[0]?.id ?? null : events.at(-1)?.id ?? null;
  }

  const index = events.findIndex((event) => event.id === selectedEventId);
  if (index === -1) {
    return direction > 0 ? events[0]?.id ?? null : events.at(-1)?.id ?? null;
  }

  const nextIndex = Math.max(0, Math.min(events.length - 1, index + direction));
  return events[nextIndex]?.id ?? null;
}

function getVisibleEvents(events: EventRecord[], ui: BlockUiState): EventRecord[] {
  return events
    .filter((event) => eventVisibleAtVerbosity(event, ui.verbosity))
    .filter((event) => eventMatchesFilters(event, ui.filters));
}

function resolveSelectedEventId(events: EventRecord[], ui: BlockUiState): string | null {
  const visibleEvents = getVisibleEvents(events, ui);

  if (visibleEvents.length === 0) {
    return null;
  }

  if (ui.followEvents || !ui.selectedEventId) {
    return visibleEvents.at(-1)?.id ?? null;
  }

  if (visibleEvents.some((event) => event.id === ui.selectedEventId)) {
    return ui.selectedEventId;
  }

  return visibleEvents.at(-1)?.id ?? null;
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
          content: state.activeStream?.content ?? "",
          tools: state.activeStream?.tools ?? [],
          isThinking: true,
          startedAt: state.activeStream?.startedAt ?? Date.now(),
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
        scrollOffset: 0,
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
      if (stream.tools.some((t) => t.callId === action.callId)) {
        return state;
      }
      const tool: ToolSummary = {
        name: action.name,
        callId: action.callId,
        arguments: action.arguments,
        status: "running",
        startedAt: Date.now(),
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
          tools: state.activeStream.tools.map((tool) =>
            tool.callId === action.callId
              ? {
                  ...tool,
                  result: action.result,
                  error: action.error,
                  durationMs: action.durationMs,
                  status: (action.error ? "failed" : "completed") as
                    | "completed"
                    | "failed",
                }
              : tool,
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
        permissions: state.permissions.filter((permission) => permission.status === "pending"),
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
        permissions: state.permissions.map((permission) =>
          permission.id === action.id
            ? { ...permission, status: resolvePermissionStatus(action.decision) }
            : permission,
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

    case "EVENT_RECEIVED": {
      const events = [...state.events, action.event].slice(-MAX_EVENTS);
      const nextUi = { ...state.ui };
      return {
        ...state,
        events,
        runs: updateRuns(state.runs, action.event),
        ui: {
          ...nextUi,
          selectedEventId: resolveSelectedEventId(events, nextUi),
        },
      };
    }

    case "SET_VERBOSITY": {
      const nextUi = {
        ...state.ui,
        verbosity: action.verbosity,
        showEventPane: action.verbosity !== "compact",
      };
      return {
        ...state,
        ui: {
          ...nextUi,
          selectedEventId: resolveSelectedEventId(state.events, nextUi),
        },
      };
    }

    case "TOGGLE_EVENT_PANE": {
      return {
        ...state,
        ui: {
          ...state.ui,
          showEventPane: !state.ui.showEventPane,
        },
      };
    }

    case "SELECT_EVENT": {
      return {
        ...state,
        ui: {
          ...state.ui,
          selectedEventId: action.eventId,
          followEvents: action.eventId === null,
        },
      };
    }

    case "SELECT_NEXT_EVENT": {
      const visibleEvents = getVisibleEvents(state.events, state.ui);
      return {
        ...state,
        ui: {
          ...state.ui,
          selectedEventId: cycleSelection(visibleEvents, state.ui.selectedEventId, 1),
          followEvents: false,
        },
      };
    }

    case "SELECT_PREV_EVENT": {
      const visibleEvents = getVisibleEvents(state.events, state.ui);
      return {
        ...state,
        ui: {
          ...state.ui,
          selectedEventId: cycleSelection(visibleEvents, state.ui.selectedEventId, -1),
          followEvents: false,
        },
      };
    }

    case "SET_EVENT_FOLLOW": {
      const nextUi = {
        ...state.ui,
        followEvents: action.follow,
      };
      return {
        ...state,
        ui: {
          ...nextUi,
          selectedEventId: resolveSelectedEventId(state.events, nextUi),
        },
      };
    }

    case "SET_EVENT_FILTERS": {
      const nextUi = {
        ...state.ui,
        filters: {
          ...state.ui.filters,
          ...action.filters,
        },
      };
      return {
        ...state,
        ui: {
          ...nextUi,
          selectedEventId: resolveSelectedEventId(state.events, nextUi),
        },
      };
    }

    case "CLEAR_EVENT_FILTERS": {
      const nextUi = {
        ...state.ui,
        filters: {
          categories: [],
          statuses: [],
          search: "",
        },
      };
      return {
        ...state,
        ui: {
          ...nextUi,
          selectedEventId: resolveSelectedEventId(state.events, nextUi),
        },
      };
    }

    case "AGENT_STARTED": {
      return {
        ...state,
        agents: upsertAgent(state.agents, action.agent),
      };
    }

    case "AGENT_COMPLETED": {
      return {
        ...state,
        agents: updateAgentStatus(state.agents, action),
      };
    }

    case "CLEAR_BLOCKS": {
      return {
        ...state,
        completedBlocks: [],
        activeStream: null,
        agents: [],
        permissions: [],
        error: null,
        events: [],
        runs: {},
        ui: {
          ...state.ui,
          selectedEventId: null,
          followEvents: true,
          filters: {
            categories: [],
            statuses: [],
            search: "",
          },
        },
      };
    }

    case "SCROLL_UP": {
      const delta = action.lines ?? 1;
      return { ...state, scrollOffset: state.scrollOffset + delta };
    }

    case "SCROLL_DOWN": {
      const delta = action.lines ?? 1;
      return { ...state, scrollOffset: Math.max(0, state.scrollOffset - delta) };
    }

    case "SCROLL_TO_BOTTOM": {
      return { ...state, scrollOffset: 0 };
    }

    default:
      return state;
  }
}

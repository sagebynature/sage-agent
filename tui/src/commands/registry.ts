import type { Dispatch } from "react";
import { METHODS } from "../types/protocol.js";
import type { BlockAction, BlockState } from "../state/blockReducer.js";
import type { PermissionState } from "../types/state.js";
import type { EventFilters, VerbosityMode } from "../types/events.js";
import { SHORTCUT_LABELS } from "../shortcuts.js";

type CommandDispatch = Dispatch<BlockAction>;

interface CommandClient {
  request<T = unknown>(method: string, params?: Record<string, unknown>): Promise<T>;
}

export interface CommandExecutionContext {
  client: CommandClient;
  dispatch: CommandDispatch;
  getState: () => BlockState;
  shutdown: () => void;
}

export interface CommandDefinition {
  name: string;
  description: string;
  aliases: string[];
  usage?: string;
  handler: (args: string) => string | undefined | Promise<string | undefined>;
}

interface CommandSpec {
  name: string;
  description: string;
  aliases: string[];
  usage?: string;
  createHandler: (
    context: CommandExecutionContext | undefined,
    registry: CommandRegistry,
  ) => CommandDefinition["handler"];
}

const VERBOSITY_ORDER: VerbosityMode[] = ["compact", "normal", "debug"];

function cycleVerbosity(current: VerbosityMode): VerbosityMode {
  const index = VERBOSITY_ORDER.indexOf(current);
  return VERBOSITY_ORDER[(index + 1) % VERBOSITY_ORDER.length] ?? "compact";
}

function parseKeyValueArgs(args: string): Record<string, string> {
  const pairs: Record<string, string> = {};
  const pattern = /(\w+)=("([^"]*)"|'([^']*)'|(\S+))/g;

  for (const match of args.matchAll(pattern)) {
    const [, key, , doubleQuoted, singleQuoted, bare] = match;
    if (key) {
      pairs[key] = (doubleQuoted ?? singleQuoted ?? bare ?? "").trim();
    }
  }

  return pairs;
}

function parseCsvValues(args: string, key: string): string[] {
  const value = parseKeyValueArgs(args)[key];
  return value ? value.split(",").map((entry) => entry.trim()).filter(Boolean) : [];
}

function parseSearchValue(args: string): string {
  return parseKeyValueArgs(args).search ?? "";
}

function getCurrentSessionId(state: BlockState): string | undefined {
  const activeRun = state.activeStream?.runId
    ? state.runs[state.activeStream.runId]
    : Object.values(state.runs).at(-1);
  return state.session?.id ?? activeRun?.sessionId ?? Object.values(state.runs).at(-1)?.sessionId;
}

function requireContext(
  context: CommandExecutionContext | undefined,
  commandName: string,
): CommandExecutionContext {
  if (!context) {
    throw new Error(`Command '${commandName}' requires an execution context`);
  }
  return context;
}

async function clearCurrentSession(
  context: CommandExecutionContext,
  state: BlockState,
): Promise<void> {
  const currentSessionId = getCurrentSessionId(state);
  if (!currentSessionId) {
    return;
  }

  const response = await context.client.request<{ cleared: boolean }>(
    METHODS.SESSION_CLEAR,
    { sessionId: currentSessionId },
  );
  if (!response.cleared) {
    throw new Error(`Session ${currentSessionId} could not be cleared`);
  }
}

function formatPendingPermissions(permissions: PermissionState[]): string {
  return permissions.length === 0
    ? "No pending permission requests."
    : permissions.map((permission) => `[${permission.status}] ${permission.tool}: ${JSON.stringify(permission.arguments)}`).join("\n");
}

function formatHelp(registry: CommandRegistry): string {
  const commandLines = registry.getAll().map((command) =>
    `/${command.name}${command.usage ? ` ${command.usage}` : ""} — ${command.description}`
  );

  const shortcutLines = [
    `${SHORTCUT_LABELS.toggleVerbosity} — Cycle event verbosity`,
    `${SHORTCUT_LABELS.toggleEventPane} — Toggle event pane`,
    `${SHORTCUT_LABELS.clear} — Clear conversation`,
    `${SHORTCUT_LABELS.reset} — Reset session and state`,
    `${SHORTCUT_LABELS.approvePermission} — Approve first pending permission`,
    `${SHORTCUT_LABELS.saveSession} — Save session feedback`,
    "PageUp/PageDown — Scroll inspector",
    `${SHORTCUT_LABELS.previousEvent}/${SHORTCUT_LABELS.nextEvent} — Previous/next selected event`,
  ];

  return [...commandLines, ...shortcutLines].join("\n");
}

const COMMAND_SPECS: CommandSpec[] = [
  {
    name: "help",
    description: "Show help and available commands",
    aliases: ["h", "?"],
    createHandler: (_context, registry) => () => formatHelp(registry),
  },
  {
    name: "clear",
    description: "Clear conversation",
    aliases: ["cls"],
    createHandler: (context) => async () => {
      const runtime = requireContext(context, "clear");
      await clearCurrentSession(runtime, runtime.getState());
      runtime.dispatch({ type: "CLEAR_BLOCKS" });
      return "Conversation cleared.";
    },
  },
  {
    name: "reset",
    description: "Reset session and state",
    aliases: ["restart"],
    createHandler: (context) => async () => {
      const runtime = requireContext(context, "reset");
      await clearCurrentSession(runtime, runtime.getState());
      runtime.dispatch({ type: "CLEAR_BLOCKS" });
      runtime.dispatch({ type: "SET_SESSION", session: null });
      runtime.dispatch({
        type: "UPDATE_USAGE",
        usage: {
          promptTokens: 0,
          completionTokens: 0,
          totalCost: 0,
          model: "",
          contextUsagePercent: 0,
        },
      });
      return "Session reset.";
    },
  },
  {
    name: "session",
    description: "Show current session info",
    aliases: [],
    createHandler: (context) => () => {
      const runtime = requireContext(context, "session");
      const state = runtime.getState();
      return state.session
        ? `Session: ${state.session.id}\nAgent: ${state.session.agentName}\nMessages: ${state.session.messageCount}`
        : "No active session.";
    },
  },
  {
    name: "sessions",
    description: "List sessions",
    aliases: [],
    createHandler: (context) => async () => {
      const runtime = requireContext(context, "sessions");
      const result = await runtime.client.request(METHODS.SESSION_LIST, {});
      return JSON.stringify(result, null, 2);
    },
  },
  {
    name: "compact",
    description: "Compact context history",
    aliases: [],
    createHandler: (context) => async () => {
      const runtime = requireContext(context, "compact");
      const result = await runtime.client.request("agent/compact", {});
      return JSON.stringify(result, null, 2);
    },
  },
  {
    name: "model",
    description: "Show current model",
    aliases: [],
    createHandler: (context) => async () => {
      const runtime = requireContext(context, "model");
      const result = await runtime.client.request(METHODS.CONFIG_GET, { key: "model" });
      return `Current model: ${JSON.stringify(result)}`;
    },
  },
  {
    name: "models",
    description: "Show model configuration",
    aliases: [],
    createHandler: (context) => async () => {
      const runtime = requireContext(context, "models");
      const result = await runtime.client.request(METHODS.CONFIG_GET, { key: "model" });
      return `Current model: ${JSON.stringify(result)}`;
    },
  },
  {
    name: "usage",
    description: "Show token usage statistics",
    aliases: [],
    createHandler: (context) => () => {
      const runtime = requireContext(context, "usage");
      const usage = runtime.getState().usage;
      return [
        `Model: ${usage.model || "unknown"}`,
        `Prompt tokens: ${usage.promptTokens}`,
        `Completion tokens: ${usage.completionTokens}`,
        `Cost: $${usage.totalCost.toFixed(4)}`,
        `Context: ${usage.contextUsagePercent}%`,
      ].join("\n");
    },
  },
  {
    name: "tools",
    description: "List available tools",
    aliases: [],
    createHandler: (context) => async () => {
      const runtime = requireContext(context, "tools");
      const result = await runtime.client.request(METHODS.TOOLS_LIST, {});
      return JSON.stringify(result, null, 2);
    },
  },
  {
    name: "permissions",
    description: "Show pending permission requests",
    aliases: ["perms"],
    createHandler: (context) => () => {
      const runtime = requireContext(context, "permissions");
      const pending = runtime.getState().permissions.filter((permission) => permission.status === "pending");
      return formatPendingPermissions(pending);
    },
  },
  {
    name: "verbosity",
    description: "Set event verbosity level",
    aliases: ["verb"],
    usage: "[compact|normal|debug]",
    createHandler: (context) => (args) => {
      const runtime = requireContext(context, "verbosity");
      const state = runtime.getState();
      const nextVerbosity = (args.trim().toLowerCase() || cycleVerbosity(state.ui.verbosity)) as VerbosityMode;
      if (!VERBOSITY_ORDER.includes(nextVerbosity)) {
        return `Unknown verbosity: ${args || "empty"}`;
      }
      runtime.dispatch({ type: "SET_VERBOSITY", verbosity: nextVerbosity });
      return `Verbosity set to ${nextVerbosity}.`;
    },
  },
  {
    name: "events",
    description: "Control the event pane",
    aliases: [],
    usage: "[show|hide|toggle|next|prev|follow]",
    createHandler: (context) => (args) => {
      const runtime = requireContext(context, "events");
      const state = runtime.getState();
      const subcommand = args.trim().toLowerCase();

      if (subcommand === "show") {
        if (!state.ui.showEventPane) {
          runtime.dispatch({ type: "TOGGLE_EVENT_PANE" });
        }
        return "Event pane shown.";
      }
      if (subcommand === "hide") {
        if (state.ui.showEventPane) {
          runtime.dispatch({ type: "TOGGLE_EVENT_PANE" });
        }
        return "Event pane hidden.";
      }
      if (subcommand === "next") {
        runtime.dispatch({ type: "SELECT_NEXT_EVENT" });
        return "Selected next event.";
      }
      if (subcommand === "prev") {
        runtime.dispatch({ type: "SELECT_PREV_EVENT" });
        return "Selected previous event.";
      }
      if (subcommand === "follow" || subcommand === "follow on") {
        runtime.dispatch({ type: "SET_EVENT_FOLLOW", follow: true });
        return "Event follow enabled.";
      }
      if (subcommand === "follow off") {
        runtime.dispatch({ type: "SET_EVENT_FOLLOW", follow: false });
        return "Event follow disabled.";
      }

      runtime.dispatch({ type: "TOGGLE_EVENT_PANE" });
      return `Event pane ${state.ui.showEventPane ? "hidden" : "shown"}.`;
    },
  },
  {
    name: "filters",
    description: "Filter the event feed",
    aliases: [],
    usage: "[category=tool,llm] [status=error] [search=text]",
    createHandler: (context) => (args) => {
      const runtime = requireContext(context, "filters");
      const raw = args.trim();
      if (raw === "clear") {
        runtime.dispatch({ type: "CLEAR_EVENT_FILTERS" });
        return "Event filters cleared.";
      }
      runtime.dispatch({
        type: "SET_EVENT_FILTERS",
        filters: {
          categories: parseCsvValues(raw, "category") as EventFilters["categories"],
          statuses: parseCsvValues(raw, "status") as EventFilters["statuses"],
          search: parseSearchValue(raw),
        },
      });
      return "Event filters updated.";
    },
  },
  {
    name: "theme",
    description: "Change UI theme (planned)",
    aliases: [],
    createHandler: () => () => "Theme switching is not yet available.",
  },
  {
    name: "split",
    description: "Change split view (planned)",
    aliases: [],
    createHandler: () => () => "Split view is not yet available.",
  },
  {
    name: "agent",
    description: "Show active agent status",
    aliases: [],
    createHandler: (context) => () => {
      const runtime = requireContext(context, "agent");
      const active = runtime.getState().agents.filter((agent) => agent.status === "active");
      return active.length === 0
        ? "No active agents."
        : active.map((agent) => `${agent.name} [${agent.status}] — ${agent.task ?? "no task"}`).join("\n");
    },
  },
  {
    name: "agents",
    description: "List all known agents",
    aliases: [],
    createHandler: (context) => () => {
      const runtime = requireContext(context, "agents");
      const agents = runtime.getState().agents;
      return agents.length === 0
        ? "No agents."
        : agents.map((agent) => `${agent.name} [${agent.status}]`).join("\n");
    },
  },
  {
    name: "plan",
    description: "Show plan view (planned)",
    aliases: [],
    createHandler: () => () => "Plan view is not yet available.",
  },
  {
    name: "notepad",
    description: "Open scratchpad (planned)",
    aliases: ["note"],
    createHandler: () => () => "Notepad is not yet available.",
  },
  {
    name: "bg",
    description: "Manage background tasks (planned)",
    aliases: ["background"],
    createHandler: () => () => "No background tasks tracked.",
  },
  {
    name: "diff",
    description: "Show diff of last changes (planned)",
    aliases: [],
    createHandler: () => () => "Diff view is not yet available.",
  },
  {
    name: "export",
    description: "Export session transcript",
    aliases: [],
    createHandler: (context) => () => {
      const runtime = requireContext(context, "export");
      const lines = ["# Session Export", ""];
      for (const block of runtime.getState().completedBlocks) {
        if (block.type === "user") {
          lines.push(`## You\n${block.content}\n`);
        } else if (block.type === "text") {
          lines.push(`## Assistant\n${block.content}\n`);
        } else if (block.type === "tool") {
          lines.push(`## Tool: ${block.content}\n`);
        } else if (block.type === "system") {
          lines.push(`> ${block.content}\n`);
        }
      }
      return lines.join("\n");
    },
  },
  {
    name: "quit",
    description: "Exit the application",
    aliases: ["exit", "q"],
    createHandler: (context) => () => {
      const runtime = requireContext(context, "quit");
      runtime.shutdown();
      return undefined;
    },
  },
];

export class CommandRegistry {
  private commands: Map<string, CommandDefinition> = new Map();

  constructor(context?: CommandExecutionContext) {
    this.registerDefaults(context);
  }

  register(command: CommandDefinition): void {
    this.commands.set(command.name, command);
  }

  getAll(): CommandDefinition[] {
    return Array.from(this.commands.values());
  }

  find(name: string): CommandDefinition | undefined {
    const lowerName = name.toLowerCase();
    for (const command of this.commands.values()) {
      if (command.name === lowerName || command.aliases.includes(lowerName)) {
        return command;
      }
    }
    return undefined;
  }

  search(query: string): CommandDefinition[] {
    if (!query) {
      return this.getAll();
    }

    const lowerQuery = query.toLowerCase();
    const matches = Array.from(this.commands.values()).filter((command) =>
      command.name.toLowerCase().includes(lowerQuery)
      || command.description.toLowerCase().includes(lowerQuery)
      || command.aliases.some((alias) => alias.toLowerCase().includes(lowerQuery))
    );

    return matches.sort((left, right) => {
      const leftName = left.name.toLowerCase();
      const rightName = right.name.toLowerCase();

      const leftStarts = leftName.startsWith(lowerQuery);
      const rightStarts = rightName.startsWith(lowerQuery);
      if (leftStarts && !rightStarts) return -1;
      if (!leftStarts && rightStarts) return 1;

      const leftNameMatch = leftName.includes(lowerQuery);
      const rightNameMatch = rightName.includes(lowerQuery);
      if (leftNameMatch && !rightNameMatch) return -1;
      if (!leftNameMatch && rightNameMatch) return 1;

      if (leftName.length !== rightName.length) {
        return leftName.length - rightName.length;
      }

      return 0;
    });
  }

  private registerDefaults(context?: CommandExecutionContext): void {
    for (const spec of COMMAND_SPECS) {
      this.register({
        name: spec.name,
        description: spec.description,
        aliases: spec.aliases,
        ...(spec.usage ? { usage: spec.usage } : {}),
        handler: spec.createHandler(context, this),
      });
    }
  }
}

export const commandRegistry = new CommandRegistry();

import { Box, Text, useInput } from "ink";
import { type ReactNode, useCallback, useEffect, useRef } from "react";
import { SageClient } from "../ipc/client.js";
import { SageClientContext, useSageClient, useClientStatus } from "../ipc/hooks.js";
import { METHODS } from "../types/protocol.js";
import { BlockProvider, useBlocks } from "../state/BlockContext.js";
import { BlockEventRouter } from "../integration/BlockEventRouter.js";
import type { BlockState } from "../state/blockReducer.js";
import type { PermissionDecision } from "../types/state.js";
import { eventMatchesFilters, eventVisibleAtVerbosity, type VerbosityMode } from "../types/events.js";
import { ConversationView } from "./ConversationView.js";
import { InputPrompt } from "./InputPrompt.js";
import { BottomBar } from "./BottomBar.js";
import { PermissionPrompt } from "./PermissionPrompt.js";
import { useResizeHandler } from "../hooks/useResizeHandler.js";
import { EventTimeline } from "./EventTimeline.js";
import { EventInspector } from "./EventInspector.js";
import { AgentTree } from "./AgentTree.js";

const NOTIFICATION_METHODS = [
  METHODS.EVENT_EMITTED,
  METHODS.STREAM_DELTA,
  METHODS.TOOL_STARTED,
  METHODS.TOOL_COMPLETED,
  METHODS.RUN_COMPLETED,
  METHODS.DELEGATION_STARTED,
  METHODS.DELEGATION_COMPLETED,
  METHODS.BACKGROUND_COMPLETED,
  METHODS.PERMISSION_REQUEST,
  METHODS.USAGE_UPDATE,
  METHODS.COMPACTION_STARTED,
  METHODS.ERROR,
  METHODS.TURN_STARTED,
  METHODS.TURN_COMPLETED,
] as const;

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

function AppShell(): ReactNode {
  const { state, dispatch } = useBlocks();
  const client = useSageClient();
  const connectionStatus = useClientStatus();
  const { width: columns } = useResizeHandler();
  const stateRef = useRef<BlockState>(state);
  stateRef.current = state;
  const visibleEvents = state.events
    .filter((event) => eventVisibleAtVerbosity(event, state.ui.verbosity))
    .filter((event) => eventMatchesFilters(event, state.ui.filters));
  const selectedEvent = visibleEvents.find((event) => event.id === state.ui.selectedEventId)
    ?? state.events.find((event) => event.id === state.ui.selectedEventId)
    ?? visibleEvents.at(-1)
    ?? null;
  const activeRun = state.activeStream?.runId
    ? state.runs[state.activeStream.runId]
    : Object.values(state.runs).at(-1);
  const stackEventPane = state.ui.showEventPane && columns < 100;
  const eventPaneWidth = state.ui.showEventPane && !stackEventPane
    ? Math.max(36, Math.floor(columns * 0.38))
    : columns;
  const conversationWidth = state.ui.showEventPane && !stackEventPane
    ? Math.max(40, columns - eventPaneWidth - 1)
    : columns;

  useEffect(() => {
    const router = new BlockEventRouter(dispatch);

    const unsubscribers = NOTIFICATION_METHODS.map((method) =>
      client.onNotification(method, (params) => {
        router.handleNotification(method, params);
      }),
    );

    client.spawn().catch((err: unknown) => {
      dispatch({
        type: "SET_ERROR",
        error: err instanceof Error ? err.message : "Failed to connect to backend",
      });
    });

    return () => {
      for (const unsub of unsubscribers) {
        unsub();
      }
      client.dispose();
    };
  }, [client, dispatch]);

  const handleSubmit = useCallback(
    async (text: string) => {
      if (connectionStatus !== "connected") return;

      dispatch({ type: "SUBMIT_MESSAGE", content: text });

      try {
        const response = await client.request<{ runId: string }>(METHODS.AGENT_RUN, { message: text });
        if (response && response.runId) {
          dispatch({ type: "STREAM_START", runId: response.runId });
        }
      } catch (err: unknown) {
        dispatch({ type: "STREAM_END", status: "error", error: err instanceof Error ? err.message : "Failed to send message" });
      }
    },
    [client, connectionStatus, dispatch],
  );

  const handleCancel = useCallback(async () => {
    dispatch({ type: "STREAM_END", status: "cancelled" });
    try {
      await client.request(METHODS.AGENT_CANCEL, {});
    } catch {
      // Best effort
    }
  }, [client, dispatch]);

  const handlePermissionRespond = useCallback(
    async (id: string, decision: PermissionDecision, modifiedArgs?: Record<string, unknown>) => {
      dispatch({ type: "PERMISSION_RESPOND", id, decision });
      try {
        await client.request(METHODS.PERMISSION_RESPOND, {
          request_id: id,
          decision,
          ...(modifiedArgs ? { arguments: modifiedArgs } : {}),
        });
      } catch {
        // Best effort
      }
    },
    [client, dispatch],
  );

  const handleCommand = useCallback(
    async (commandName: string, _args: string) => {
      const cmd = commandName.replace(/^\//, "").toLowerCase();
      let result: string | undefined;

      try {
        switch (cmd) {
          case "help": {
            const commands = [
              "/help — Show available commands",
              "/clear — Clear conversation",
              "/reset — Reset session and state",
              "/session — Show current session info",
              "/sessions — List and switch sessions",
              "/compact — Compact context history",
              "/model — Show current model",
              "/models — List available models",
              "/usage — Show token usage statistics",
              "/tools — List available tools",
              "/permissions — Show permission grants",
              "/verbosity [compact|normal|debug] — Set event verbosity",
              "/events [show|hide|toggle|next|prev|follow] — Event pane controls",
              "/filters [category=tool,llm] [status=error] [search=text] — Event filters",
              "/agent — Show active agents",
              "/agents — List all agents",
              "/export — Export session transcript",
              "/theme — Change UI theme (planned)",
              "/split — Split view (planned)",
              "/plan — Show plan (planned)",
              "/notepad — Open scratchpad (planned)",
              "/bg — Background tasks (planned)",
              "/diff — Show diff (planned)",
              "/quit — Exit",
            ];
            result = commands.join("\n");
            break;
          }
          case "clear":
            if (getCurrentSessionId(stateRef.current)) {
              const currentSessionId = getCurrentSessionId(stateRef.current)!;
              const response = await client.request<{ cleared: boolean }>(METHODS.SESSION_CLEAR, {
                sessionId: currentSessionId,
              });
              if (!response.cleared) {
                throw new Error(`Session ${currentSessionId} could not be cleared`);
              }
            }
            dispatch({ type: "CLEAR_BLOCKS" });
            result = "Conversation cleared.";
            break;
          case "reset":
          case "restart":
            if (getCurrentSessionId(stateRef.current)) {
              const currentSessionId = getCurrentSessionId(stateRef.current)!;
              const response = await client.request<{ cleared: boolean }>(METHODS.SESSION_CLEAR, {
                sessionId: currentSessionId,
              });
              if (!response.cleared) {
                throw new Error(`Session ${currentSessionId} could not be cleared`);
              }
            }
            dispatch({ type: "CLEAR_BLOCKS" });
            dispatch({ type: "SET_SESSION", session: null });
            dispatch({
              type: "UPDATE_USAGE",
              usage: { promptTokens: 0, completionTokens: 0, totalCost: 0, model: "", contextUsagePercent: 0 },
            });
            result = "Session reset.";
            break;
          case "session":
            result = stateRef.current.session
              ? `Session: ${stateRef.current.session.id}\nAgent: ${stateRef.current.session.agentName}\nMessages: ${stateRef.current.session.messageCount}`
              : "No active session.";
            break;
          case "sessions": {
            const r = await client.request("session/list", {});
            result = JSON.stringify(r, null, 2);
            break;
          }
          case "compact": {
            const r = await client.request("agent/compact", {});
            result = JSON.stringify(r, null, 2);
            break;
          }
          case "model": {
            const r = await client.request("config/get", { key: "model" });
            result = `Current model: ${JSON.stringify(r)}`;
            break;
          }
          case "models": {
            const r = await client.request("config/get", { key: "model" });
            result = `Current model: ${JSON.stringify(r)}`;
            break;
          }
          case "usage":
            result = [
              `Model: ${stateRef.current.usage.model || "unknown"}`,
              `Prompt tokens: ${stateRef.current.usage.promptTokens}`,
              `Completion tokens: ${stateRef.current.usage.completionTokens}`,
              `Cost: $${stateRef.current.usage.totalCost.toFixed(4)}`,
              `Context: ${stateRef.current.usage.contextUsagePercent}%`,
            ].join("\n");
            break;
          case "tools": {
            const r = await client.request("tools/list", {});
            result = JSON.stringify(r, null, 2);
            break;
          }
          case "permissions":
          case "perms": {
            const pending = stateRef.current.permissions.filter((p) => p.status === "pending");
            result = pending.length === 0
              ? "No pending permission requests."
              : pending.map((p) => `[${p.status}] ${p.tool}: ${JSON.stringify(p.arguments)}`).join("\n");
            break;
          }
          case "verbosity": {
            const nextVerbosity = (_args.trim().toLowerCase() || cycleVerbosity(stateRef.current.ui.verbosity)) as VerbosityMode;
            if (!VERBOSITY_ORDER.includes(nextVerbosity)) {
              result = `Unknown verbosity: ${_args || "empty"}`;
              break;
            }
            dispatch({ type: "SET_VERBOSITY", verbosity: nextVerbosity });
            result = `Verbosity set to ${nextVerbosity}.`;
            break;
          }
          case "events": {
            const subcommand = _args.trim().toLowerCase();
            if (subcommand === "show") {
              if (!stateRef.current.ui.showEventPane) {
                dispatch({ type: "TOGGLE_EVENT_PANE" });
              }
              result = "Event pane shown.";
              break;
            }
            if (subcommand === "hide") {
              if (stateRef.current.ui.showEventPane) {
                dispatch({ type: "TOGGLE_EVENT_PANE" });
              }
              result = "Event pane hidden.";
              break;
            }
            if (subcommand === "next") {
              dispatch({ type: "SELECT_NEXT_EVENT" });
              result = "Selected next event.";
              break;
            }
            if (subcommand === "prev") {
              dispatch({ type: "SELECT_PREV_EVENT" });
              result = "Selected previous event.";
              break;
            }
            if (subcommand === "follow" || subcommand === "follow on") {
              dispatch({ type: "SET_EVENT_FOLLOW", follow: true });
              result = "Event follow enabled.";
              break;
            }
            if (subcommand === "follow off") {
              dispatch({ type: "SET_EVENT_FOLLOW", follow: false });
              result = "Event follow disabled.";
              break;
            }
            dispatch({ type: "TOGGLE_EVENT_PANE" });
            result = `Event pane ${stateRef.current.ui.showEventPane ? "hidden" : "shown"}.`;
            break;
          }
          case "filters": {
            const raw = _args.trim();
            if (raw === "clear") {
              dispatch({ type: "CLEAR_EVENT_FILTERS" });
              result = "Event filters cleared.";
              break;
            }
            dispatch({
              type: "SET_EVENT_FILTERS",
              filters: {
                categories: parseCsvValues(raw, "category") as typeof stateRef.current.ui.filters.categories,
                statuses: parseCsvValues(raw, "status") as typeof stateRef.current.ui.filters.statuses,
                search: parseSearchValue(raw),
              },
            });
            result = "Event filters updated.";
            break;
          }
          case "agent": {
            const active = stateRef.current.agents.filter((a) => a.status === "active");
            result = active.length === 0
              ? "No active agents."
              : active.map((a) => `${a.name} [${a.status}] — ${a.task ?? "no task"}`).join("\n");
            break;
          }
          case "agents": {
            result = stateRef.current.agents.length === 0
              ? "No agents."
              : stateRef.current.agents.map((a) => `${a.name} [${a.status}]`).join("\n");
            break;
          }
          case "export": {
            const lines = ["# Session Export", ""];
            for (const block of stateRef.current.completedBlocks) {
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
            result = lines.join("\n");
            break;
          }
          case "quit":
          case "exit":
          case "q":
            shutdown();
            break;
          // Honest stubs
          case "theme":
            result = "Theme switching is not yet available.";
            break;
          case "split":
            result = "Split view is not yet available.";
            break;
          case "plan":
            result = "Plan view is not yet available.";
            break;
          case "notepad":
          case "note":
            result = "Notepad is not yet available.";
            break;
          case "bg":
          case "background":
            result = "No background tasks tracked.";
            break;
          case "diff":
            result = "Diff view is not yet available.";
            break;
          default:
            result = `Unknown command: /${cmd}. Type /help for available commands.`;
        }
      } catch (err: unknown) {
        result = `Command failed: ${err instanceof Error ? err.message : String(err)}`;
      }

      if (result) {
        dispatch({ type: "ADD_SYSTEM_BLOCK", content: result });
      }
    },
    [client, dispatch],
  );

  const shutdown = useCallback(() => {
    client.dispose();
    process.exit(0);
  }, [client]);

  useInput((input, key) => {
    // Cancel / quit
    if (key.ctrl && input === "c") {
      if (state.activeStream) {
        void handleCancel();
      } else {
        shutdown();
      }
      return;
    }

    // Escape: cancel stream or dismiss error
    if (key.escape) {
      if (state.activeStream) {
        void handleCancel();
      } else if (state.error) {
        dispatch({ type: "CLEAR_ERROR" });
      }
      return;
    }

    // Ctrl+L: clear
    if (key.ctrl && input === "l") {
      void handleCommand("/clear", "");
      return;
    }

    // Ctrl+N: new session (reset)
    if (key.ctrl && input === "n") {
      void handleCommand("/reset", "");
      return;
    }

    // Ctrl+P: approve first pending permission
    if (key.ctrl && input === "p") {
      const pending = stateRef.current.permissions.find((p) => p.status === "pending");
      if (pending) {
        void handlePermissionRespond(pending.id, "allow_once");
      }
      return;
    }

    // Ctrl+S: save feedback
    if (key.ctrl && input === "s") {
      dispatch({ type: "ADD_SYSTEM_BLOCK", content: "Session auto-saved." });
      return;
    }

    if (key.ctrl && input === "v") {
      dispatch({ type: "SET_VERBOSITY", verbosity: cycleVerbosity(stateRef.current.ui.verbosity) });
      return;
    }

    if (key.ctrl && input === "e") {
      dispatch({ type: "TOGGLE_EVENT_PANE" });
      return;
    }

    if (key.ctrl && input === "j") {
      dispatch({ type: "SELECT_NEXT_EVENT" });
      return;
    }

    if (key.ctrl && input === "k") {
      dispatch({ type: "SELECT_PREV_EVENT" });
      return;
    }

    // Scroll: Ctrl+Up / Ctrl+Down
    if (key.ctrl && key.upArrow) {
      dispatch({ type: "SCROLL_UP" });
      return;
    }
    if (key.ctrl && key.downArrow) {
      dispatch({ type: "SCROLL_DOWN" });
      return;
    }
  });

  const pendingPermissions = state.permissions.filter((p) => p.status === "pending");

  return (
    <Box flexDirection="column" width={columns}>
      <Box flexDirection={stackEventPane ? "column" : "row"} width={columns}>
        <ConversationView
          completedBlocks={state.completedBlocks}
          activeStream={state.activeStream}
          width={conversationWidth}
        />
        {state.ui.showEventPane && (
          <Box
            flexDirection="column"
            width={eventPaneWidth}
            marginLeft={stackEventPane ? 0 : 1}
            marginTop={stackEventPane ? 1 : 0}
          >
            <EventTimeline
              events={state.events}
              selectedEventId={selectedEvent?.id ?? null}
              verbosity={state.ui.verbosity}
              filters={state.ui.filters}
            />
            <Box marginTop={1}>
              <EventInspector event={selectedEvent} />
            </Box>
            <Box marginTop={1}>
              <AgentTree />
            </Box>
          </Box>
        )}
      </Box>
      {state.error && (
        <Box>
          <Text color="red">{"● Error: "}{state.error}</Text>
        </Box>
      )}
      {pendingPermissions.map((perm) => (
        <PermissionPrompt
          key={perm.id}
          request={perm}
          onRespond={handlePermissionRespond}
        />
      ))}
      <InputPrompt
        onSubmit={handleSubmit}
        onCommand={handleCommand}
        isActive={!state.activeStream && connectionStatus === "connected" && pendingPermissions.length === 0}
        width={columns}
      />
      <BottomBar
        usage={state.usage}
        activeStream={state.activeStream}
        permissions={state.permissions}
        error={state.error}
        connectionStatus={connectionStatus}
        agents={state.agents}
        sessionName={state.session?.agentName}
        verbosity={state.ui.verbosity}
        showEventPane={state.ui.showEventPane}
        activeRun={activeRun}
        selectedEvent={selectedEvent}
      />
    </Box>
  );
}

export function App(): ReactNode {
  const clientRef = useRef(new SageClient());

  return (
    <SageClientContext value={clientRef.current}>
      <BlockProvider>
        <AppShell />
      </BlockProvider>
    </SageClientContext>
  );
}

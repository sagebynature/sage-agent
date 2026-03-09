import { Box, Text, useInput } from "ink";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SageClient } from "../ipc/client.js";
import { SageClientContext, useSageClient, useClientStatus } from "../ipc/hooks.js";
import type { SageClientOptions } from "../ipc/types.js";
import { METHODS } from "../types/protocol.js";
import { BlockProvider, useBlocks } from "../state/BlockContext.js";
import { BlockEventRouter } from "../integration/BlockEventRouter.js";
import type { BlockAction, BlockState } from "../state/blockReducer.js";
import type { PermissionDecision } from "../types/state.js";
import { eventMatchesFilters, eventVisibleAtVerbosity, type VerbosityMode } from "../types/events.js";
import { ConversationView } from "./ConversationView.js";
import { InputPrompt, type InputPromptHandle } from "./InputPrompt.js";
import { BottomBar } from "./BottomBar.js";
import { PermissionPrompt } from "./PermissionPrompt.js";
import { useResizeHandler } from "../hooks/useResizeHandler.js";
import { EventTimeline } from "./EventTimeline.js";
import { ComplexityPanel } from "./ComplexityPanel.js";
import { EventInspector } from "./EventInspector.js";
import { ActiveTaskDock } from "./ActiveTaskDock.js";


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

/**
 * Batches rapid dispatch calls into a single BATCH action per microtask.
 * This prevents flickering caused by many individual state updates during
 * event bursts (e.g. streaming deltas, tool start/complete, run lifecycle).
 */
function useBatchedDispatch(dispatch: React.Dispatch<BlockAction>): (action: BlockAction) => void {
  const queueRef = useRef<BlockAction[]>([]);
  const scheduledRef = useRef(false);

  return useCallback(
    (action: BlockAction) => {
      queueRef.current.push(action);
      if (!scheduledRef.current) {
        scheduledRef.current = true;
        queueMicrotask(() => {
          scheduledRef.current = false;
          const actions = queueRef.current.splice(0);
          if (actions.length === 1) {
            dispatch(actions[0]!);
          } else if (actions.length > 1) {
            dispatch({ type: "BATCH", actions });
          }
        });
      }
    },
    [dispatch],
  );
}

function AppShell(): ReactNode {
  const { state, dispatch } = useBlocks();
  const client = useSageClient();
  const connectionStatus = useClientStatus();
  const { width: columns, height: rows } = useResizeHandler();
  const [mainAgentName, setMainAgentName] = useState("");
  const [configuredModel, setConfiguredModel] = useState("");
  const stateRef = useRef<BlockState>(state);
  stateRef.current = state;
  const inputRef = useRef<InputPromptHandle>(null);

  const batchedDispatch = useBatchedDispatch(dispatch);

  const visibleEvents = useMemo(
    () =>
      state.events
        .filter((event) => eventVisibleAtVerbosity(event, state.ui.verbosity))
        .filter((event) => eventMatchesFilters(event, state.ui.filters)),
    [state.events, state.ui.verbosity, state.ui.filters],
  );

  const selectedEvent = useMemo(
    () =>
      visibleEvents.find((event) => event.id === state.ui.selectedEventId)
      ?? state.events.find((event) => event.id === state.ui.selectedEventId)
      ?? visibleEvents.at(-1)
      ?? null,
    [visibleEvents, state.events, state.ui.selectedEventId],
  );

  const activeRun = state.activeStream?.runId
    ? state.runs[state.activeStream.runId]
    : Object.values(state.runs).at(-1);
  const currentMainAgentName = activeRun?.agentPath[0]
    ?? state.events.at(-1)?.agentPath[0]
    ?? state.session?.agentName
    ?? mainAgentName;
  const currentModelName = state.usage.model || configuredModel;

  useEffect(() => {
    const router = new BlockEventRouter(batchedDispatch);
    let isMounted = true;

    const unsubscribers = NOTIFICATION_METHODS.map((method) =>
      client.onNotification(method, (params) => {
        router.handleNotification(method, params);
      }),
    );

    void (async () => {
      try {
        await client.spawn();

        const [nameResponse, modelResponse] = await Promise.all([
          client.request<{ value?: unknown }>(METHODS.CONFIG_GET, { key: "name" }),
          client.request<{ value?: unknown }>(METHODS.CONFIG_GET, { key: "model" }),
        ]);

        if (isMounted && typeof nameResponse?.value === "string" && nameResponse.value.length > 0) {
          setMainAgentName(nameResponse.value);
        }
        if (isMounted && typeof modelResponse?.value === "string" && modelResponse.value.length > 0) {
          setConfiguredModel(modelResponse.value);
        }
      } catch (err: unknown) {
        dispatch({
          type: "SET_ERROR",
          error: err instanceof Error ? err.message : "Failed to connect to backend",
        });
      }
    })();

    return () => {
      isMounted = false;
      for (const unsub of unsubscribers) {
        unsub();
      }
      client.dispose();
    };
  }, [client, dispatch, batchedDispatch]);

  const handleSubmit = useCallback(
    async (text: string) => {
      if (connectionStatus !== "connected") return;

      dispatch({ type: "SUBMIT_MESSAGE", content: text });

      try {
        // The backend returns immediately with { runId } while the actual run
        // executes asynchronously.  Stream lifecycle (STREAM_START → deltas →
        // STREAM_END) is driven entirely by event notifications that arrive via
        // onNotification handlers.  Dispatching STREAM_START here would race
        // with those notifications: if the run completes before this await
        // resolves (common when readline buffers multiple lines), the late
        // STREAM_START creates a phantom empty activeStream that never ends.
        await client.request<{ runId: string }>(METHODS.AGENT_RUN, { message: text });
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
    // Cancel / clear input / quit
    if (key.ctrl && input === "c") {
      if (state.activeStream) {
        void handleCancel();
      } else if (inputRef.current?.hasValue()) {
        inputRef.current.clear();
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

    if (key.ctrl && key.pageUp) {
      dispatch({ type: "SELECT_PREV_EVENT" });
      return;
    }
    if (key.ctrl && key.pageDown) {
      dispatch({ type: "SELECT_NEXT_EVENT" });
      return;
    }
  });

  const pendingPermissions = useMemo(
    () => state.permissions.filter((p) => p.status === "pending"),
    [state.permissions],
  );

  // The event pane lives in Ink's dynamic area (below <Static> messages).
  // To keep it compact, timeline and inspector sit side-by-side in a
  // horizontal strip with a capped height.
  const eventPaneHeight = state.ui.showEventPane
    ? Math.max(8, Math.min(16, Math.floor(rows * 0.35)))
    : 0;

  return (
    <Box flexDirection="column" width={columns}>
      {/* Conversation stays purely historical in Ink's permanent area. */}
      <ConversationView
        completedBlocks={state.completedBlocks}
        width={columns}
      />
      {/* Active work is docked above the input so it stays pinned near the footer. */}
      <ActiveTaskDock
        streams={state.activeStream ? [state.activeStream] : []}
        width={columns}
      />
      {/* Event pane: compact horizontal strip in the dynamic area.
          Timeline and inspector sit side-by-side to save vertical space. */}
      {state.ui.showEventPane && (
        <Box
          flexDirection="row"
          width={columns}
          height={eventPaneHeight}
          overflowY="hidden"
        >
          <EventTimeline
            events={visibleEvents}
            selectedEventId={selectedEvent?.id ?? null}
            maxHeight={eventPaneHeight}
          />
          <ComplexityPanel event={selectedEvent} maxHeight={eventPaneHeight} />
          <EventInspector event={selectedEvent} maxHeight={eventPaneHeight} />
        </Box>
      )}
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
        ref={inputRef}
        onSubmit={handleSubmit}
        onCommand={handleCommand}
        isActive={!state.activeStream && connectionStatus === "connected" && pendingPermissions.length === 0}
        width={columns}
      />
      <Box marginTop={1}>
        <BottomBar
          width={columns}
          usage={state.usage}
          activeStream={state.activeStream}
          permissions={state.permissions}
          error={state.error}
          connectionStatus={connectionStatus}
          agents={state.agents}
          sessionName={currentMainAgentName}
          modelName={currentModelName}
          verbosity={state.ui.verbosity}
          showEventPane={state.ui.showEventPane}
          activeRun={state.activeStream ? activeRun : undefined}
          selectedEvent={state.ui.showEventPane ? selectedEvent : null}
        />
      </Box>
    </Box>
  );
}

interface AppProps {
  clientOptions?: SageClientOptions;
}

export function App(props: AppProps = {}): ReactNode {
  const clientRef = useRef(new SageClient(props.clientOptions));

  return (
    <SageClientContext value={clientRef.current}>
      <BlockProvider>
        <AppShell />
      </BlockProvider>
    </SageClientContext>
  );
}

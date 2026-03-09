import { Box, Text, useInput } from "ink";
import { type ReactNode, useCallback, useMemo, useRef, useState } from "react";
import { SageClient } from "../ipc/client.js";
import { SageClientContext, useSageClient, useClientStatus } from "../ipc/hooks.js";
import type { SageClientOptions } from "../ipc/types.js";
import { METHODS, type PermissionRespondParams } from "../types/protocol.js";
import { BlockProvider, useBlocks } from "../state/BlockContext.js";
import type { BlockState } from "../state/blockReducer.js";
import type { PermissionDecision } from "../types/state.js";
import type { VerbosityMode } from "../types/events.js";
import { ConversationView } from "./ConversationView.js";
import { InputPrompt, type InputPromptHandle } from "./InputPrompt.js";
import { BottomBar } from "./BottomBar.js";
import { PermissionPrompt } from "./PermissionPrompt.js";
import { useResizeHandler } from "../hooks/useResizeHandler.js";
import { EventTimeline } from "./EventTimeline.js";
import { ComplexityPanel, eventHasComplexityScore } from "./ComplexityPanel.js";
import { EventInspector } from "./EventInspector.js";
import { ActiveTaskDock } from "./ActiveTaskDock.js";
import { CommandRegistry } from "../commands/registry.js";
import { useAppBootstrap, useEventPaneState } from "../hooks/index.js";
import {
  isLeaderShortcut,
  resolveLeaderAction,
} from "../shortcuts.js";

const VERBOSITY_ORDER: VerbosityMode[] = ["compact", "normal", "debug"];

function cycleVerbosity(current: VerbosityMode): VerbosityMode {
  const index = VERBOSITY_ORDER.indexOf(current);
  return VERBOSITY_ORDER[(index + 1) % VERBOSITY_ORDER.length] ?? "compact";
}

function AppShell(): ReactNode {
  const { state, dispatch } = useBlocks();
  const client = useSageClient();
  const connectionStatus = useClientStatus();
  const { width: columns, height: rows } = useResizeHandler();
  const [leaderActive, setLeaderActive] = useState(false);
  const stateRef = useRef<BlockState>(state);
  stateRef.current = state;
  const inputRef = useRef<InputPromptHandle>(null);

  const { mainAgentName, configuredModel } = useAppBootstrap(client, dispatch);
  const { visibleEvents, selectedEvent, activeRun } = useEventPaneState(state);
  const showComplexityPanel = eventHasComplexityScore(selectedEvent);
  const currentMainAgentName = activeRun?.agentPath[0]
    ?? state.events.at(-1)?.agentPath[0]
    ?? state.session?.agentName
    ?? mainAgentName;
  const currentModelName = state.usage.model || configuredModel;

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
        const params: PermissionRespondParams = {
          request_id: id,
          decision,
          ...(modifiedArgs ? { arguments: modifiedArgs } : {}),
        };
        await client.request(METHODS.PERMISSION_RESPOND, params);
      } catch {
        // Best effort
      }
    },
    [client, dispatch],
  );

  const shutdown = useCallback(() => {
    client.dispose();
    process.exit(0);
  }, [client]);

  const commandRegistry = useMemo(
    () => new CommandRegistry({
      client,
      dispatch,
      getState: () => stateRef.current,
      shutdown,
    }),
    [client, dispatch, shutdown],
  );

  const handleCommand = useCallback(
    async (commandName: string, _args: string) => {
      const cmd = commandName.replace(/^\//, "").toLowerCase();
      let result: string | undefined;

      try {
        const command = commandRegistry.find(cmd);
        if (!command) {
          result = `Unknown command: /${cmd}. Type /help for available commands.`;
        } else {
          result = await command.handler(_args);
        }
      } catch (err: unknown) {
        result = `Command failed: ${err instanceof Error ? err.message : String(err)}`;
      }

      if (result) {
        dispatch({ type: "ADD_SYSTEM_BLOCK", content: result });
      }
    },
    [commandRegistry, dispatch],
  );

  useInput((input, key) => {
    // Cancel / clear input / quit
    if (key.ctrl && input === "c") {
      setLeaderActive(false);
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
      if (leaderActive) {
        setLeaderActive(false);
        return;
      }
      if (state.activeStream) {
        void handleCancel();
      } else if (state.error) {
        dispatch({ type: "CLEAR_ERROR" });
      }
      return;
    }

    if (leaderActive) {
      setLeaderActive(false);

      switch (resolveLeaderAction(input, key)) {
        case "clear":
          void handleCommand("/clear", "");
          return;
        case "reset":
          void handleCommand("/reset", "");
          return;
        case "approvePermission": {
          const pending = stateRef.current.permissions.find((p) => p.status === "pending");
          if (pending) {
            void handlePermissionRespond(pending.id, "allow_once");
          }
          return;
        }
        case "saveSession":
          dispatch({ type: "ADD_SYSTEM_BLOCK", content: "Session auto-saved." });
          return;
        case "toggleVerbosity":
          dispatch({ type: "SET_VERBOSITY", verbosity: cycleVerbosity(stateRef.current.ui.verbosity) });
          return;
        case "toggleEventPane":
          dispatch({ type: "TOGGLE_EVENT_PANE" });
          return;
        case "previousEvent":
          dispatch({ type: "SELECT_PREV_EVENT" });
          return;
        case "nextEvent":
          dispatch({ type: "SELECT_NEXT_EVENT" });
          return;
        case "cancel":
        case null:
          return;
      }
    }

    if (isLeaderShortcut(input, key)) {
      const inputSnapshot = inputRef.current?.getValue() ?? "";
      setLeaderActive(true);
      queueMicrotask(() => {
        inputRef.current?.setValue(inputSnapshot);
      });
      return;
    }
  });

  const pendingPermissions = useMemo(
    () => state.permissions.filter((p) => p.status === "pending"),
    [state.permissions],
  );
  const activePermission = pendingPermissions[0] ?? null;
  const queuedPermissionCount = Math.max(0, pendingPermissions.length - 1);

  // The event pane lives in Ink's dynamic area (below <Static> messages).
  // To keep it compact, timeline and inspector sit side-by-side in a
  // horizontal strip with a capped height.
  const eventPaneHeight = state.ui.showEventPane
    ? Math.max(8, Math.min(16, Math.floor(rows * 0.35)))
    : 0;
  const EVENT_TIMELINE_WIDTH = 80;
  const COMPLEXITY_PANEL_WIDTH = 34;
  const eventInspectorWidth = Math.max(
    24,
    columns - EVENT_TIMELINE_WIDTH - (showComplexityPanel ? COMPLEXITY_PANEL_WIDTH : 0),
  );

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
      {state.error && (
        <Box>
          <Text color="red">{"• Error: "}{state.error}</Text>
        </Box>
      )}
      {activePermission ? (
        <Box flexDirection="column">
          <PermissionPrompt
            key={activePermission.id}
            request={activePermission}
            onRespond={handlePermissionRespond}
          />
          {queuedPermissionCount > 0 ? (
            <Text dimColor>
              {`${queuedPermissionCount} more permission request${queuedPermissionCount === 1 ? "" : "s"} queued`}
            </Text>
          ) : null}
        </Box>
      ) : null}
      <InputPrompt
        ref={inputRef}
        onSubmit={handleSubmit}
        onCommand={handleCommand}
        isActive={!leaderActive && !state.activeStream && connectionStatus === "connected" && pendingPermissions.length === 0}
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
          leaderActive={leaderActive}
          activeRun={state.activeStream ? activeRun : undefined}
          selectedEvent={state.ui.showEventPane ? selectedEvent : null}
        />
      </Box>
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
          {showComplexityPanel ? (
            <ComplexityPanel event={selectedEvent} maxHeight={eventPaneHeight} />
          ) : null}
          <EventInspector
            event={selectedEvent}
            width={eventInspectorWidth}
            maxHeight={eventPaneHeight}
          />
        </Box>
      )}
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

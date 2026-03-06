import { Box, Text, useInput, useStdout } from "ink";
import React, { Suspense, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PlanProvider } from "../contexts/PlanContext.js";
import { SageClient } from "../ipc/client.js";
import { SageClientContext, useSageClient } from "../ipc/hooks.js";
import { wireIntegration } from "../integration/wiring.js";
import { AppProvider, useApp } from "../state/AppContext.js";
import type { AppState, PermissionDecision } from "../types/state.js";
import type { SessionInfo } from "../types/protocol.js";
import { METHODS } from "../types/protocol.js";
import type { ViewMode } from "../types/state.js";
import { ChatView } from "./ChatView.js";
import { ErrorStates } from "./ErrorStates.js";
import { InputArea } from "./InputArea.js";
import { SessionPicker } from "./SessionPicker.js";
import { PermissionPrompt } from "./PermissionPrompt.js";
import { StatusBarFooter, StatusBarHeader } from "./StatusBar.js";

const AgentTree = React.lazy(() =>
  import("./AgentTree.js").then((module) => ({ default: module.AgentTree })),
);
const PlanningPanel = React.lazy(() =>
  import("./PlanningPanel.js").then((module) => ({ default: module.PlanningPanel })),
);
const BackgroundTaskPanel = React.lazy(() =>
  import("./BackgroundTaskPanel.js").then((module) => ({
    default: module.BackgroundTaskPanel,
  })),
);

function MainView(): ReactNode {
  const { state, dispatch } = useApp();
  const showWelcomeHint = state.messages.length === 0 && !state.isStreaming;

  const sessions = useMemo<SessionInfo[]>(() => {
    if (!state.session) {
      return [];
    }

    return [
      {
        id: state.session.id,
        agentName: state.session.agentName,
        createdAt: state.session.createdAt,
        updatedAt: state.session.createdAt,
        messageCount: state.session.messageCount,
        model: state.session.model,
        totalCost: state.session.totalCost,
        firstMessage: state.session.lastMessage,
      },
    ];
  }, [state.session]);

  if (state.currentView === "dashboard") {
    return (
      <SessionPicker
        sessions={sessions}
        currentSessionId={state.session?.id}
        onResume={() => {
          dispatch({ type: "SET_VIEW", view: "focused" });
        }}
        onFork={() => {
          dispatch({ type: "SET_VIEW", view: "focused" });
        }}
        onDelete={() => {
          return;
        }}
        onNew={() => {
          dispatch({ type: "SET_VIEW", view: "focused" });
        }}
        onClose={() => {
          dispatch({ type: "SET_VIEW", view: "focused" });
        }}
      />
    );
  }

  if (state.currentView === "split") {
    return (
      <Box flexDirection="row" flexGrow={1}>
        <Box width="70%" paddingRight={1}>
          {showWelcomeHint && <Text dimColor>Welcome to sage-tui. Type a message to begin.</Text>}
          <ChatView />
        </Box>
        <Box
          width="30%"
          borderStyle="single"
          borderLeft
          borderColor="gray"
          paddingLeft={1}
          flexDirection="column"
        >
          <Text dimColor>Sidebar</Text>
          <Suspense fallback={<Text dimColor>Loading...</Text>}>
            <AgentTree />
            <PlanningPanel />
            <BackgroundTaskPanel tasks={[]} />
          </Suspense>
        </Box>
      </Box>
    );
  }

  return (
    <Box flexGrow={1}>
      {showWelcomeHint && <Text dimColor>Welcome to sage-tui. Type a message to begin.</Text>}
      <ChatView />
    </Box>
  );
}

function ErrorView(): ReactNode {
  const { state, dispatch } = useApp();
  if (!state.error) {
    return null;
  }

  return (
    <ErrorStates
      error={{
        type: "unknown",
        message: state.error,
      }}
      onDismiss={() => {
        dispatch({ type: "CLEAR_ERROR" });
      }}
    />
  );
}

function AppShell(): ReactNode {
  const { state, dispatch } = useApp();
  const client = useSageClient();
  const { stdout } = useStdout();
  const [columns] = useState(stdout?.columns ?? 80);
  const [rows] = useState(stdout?.rows ?? 24);
  const stateRef = useRef<AppState>(state);
  stateRef.current = state;
  const commandExecutorRef = useRef<{ execute: (cmd: string, args: string) => Promise<string | void> } | null>(null);

  useEffect(() => {
    const { cleanup, commandExecutor } = wireIntegration({
      client,
      dispatch,
      getState: () => stateRef.current,
    });
    commandExecutorRef.current = commandExecutor;

    client.spawn().catch((err: unknown) => {
      dispatch({
        type: "SET_ERROR",
        error: err instanceof Error ? err.message : "Failed to connect to backend",
      });
    });

    return () => {
      cleanup();
      client.dispose();
    };
  }, [client, dispatch]);

  const handleSubmit = useCallback(async (text: string) => {
    if (client.status !== "connected") return;

    dispatch({
      type: "ADD_MESSAGE",
      message: {
        id: `msg_${Date.now()}`,
        role: "user",
        content: text,
        timestamp: Date.now(),
        isStreaming: false,
      },
    });
    dispatch({ type: "SET_STREAMING", isStreaming: true });

    try {
      await client.request(METHODS.AGENT_RUN, { message: text });
    } catch (err: unknown) {
      dispatch({
        type: "SET_ERROR",
        error: err instanceof Error ? err.message : "Failed to send message",
      });
      dispatch({ type: "SET_STREAMING", isStreaming: false });
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
      } catch (err: unknown) {
        dispatch({
          type: "SET_ERROR",
          error: err instanceof Error ? err.message : "Failed to respond to permission",
        });
      }
    },
    [client, dispatch],
  );

  const handleCommand = useCallback(async (commandName: string, args: string) => {
    const result = await commandExecutorRef.current?.execute(commandName, args);
    if (typeof result === "string" && result.length > 0) {
      dispatch({
        type: "ADD_MESSAGE",
        message: {
          id: `cmd_${Date.now()}`,
          role: "system",
          content: result,
          timestamp: Date.now(),
          isStreaming: false,
        },
      });
    }
  }, [dispatch]);

  const handleCancel = useCallback(async () => {
    dispatch({ type: "SET_STREAMING", isStreaming: false });
    try {
      await client.request(METHODS.AGENT_CANCEL, {});
    } catch {
      // Best effort — backend may already be done
    }
  }, [client, dispatch]);

  useInput((input, key) => {
    if (key.ctrl && input === "b") {
      const nextView: ViewMode = state.currentView === "focused" ? "split" : "focused";
      dispatch({ type: "SET_VIEW", view: nextView });
      return;
    }

    if (key.ctrl && input === "c") {
      if (state.isStreaming) {
        void handleCancel();
      } else {
        process.exit(0);
      }
      return;
    }

    if (key.escape) {
      if (state.isStreaming) {
        void handleCancel();
        return;
      }

      if (state.error) {
        dispatch({ type: "CLEAR_ERROR" });
      }

      return;
    }
  });

  return (
    <Box flexDirection="column" width={columns} height={rows}>
      <Box height={1}>
        <Text bold color="cyan">
          ── sage-tui ── [{state.usage.model || "no model"}] ── [context: {state.usage.contextUsagePercent}%] ──
        </Text>
      </Box>
      <StatusBarHeader />

      <Box flexDirection="column" flexGrow={1}>
        <ErrorView />
        <MainView />
      </Box>

      <StatusBarFooter />
      {state.permissions.filter((p) => p.status === "pending").map((perm) => (
        <PermissionPrompt
          key={perm.id}
          request={perm}
          onRespond={handlePermissionRespond}
        />
      ))}
      <InputArea isActive={state.currentView !== "dashboard"} onSubmit={handleSubmit} onCommand={handleCommand} />
    </Box>
  );
}

export function App(): ReactNode {
  const clientRef = useRef(new SageClient());

  return (
    <SageClientContext value={clientRef.current}>
      <AppProvider>
        <PlanProvider>
          <AppShell />
        </PlanProvider>
      </AppProvider>
    </SageClientContext>
  );
}

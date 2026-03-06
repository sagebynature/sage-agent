import { Box, Text, useInput, useStdout } from "ink";
import React, { Suspense, type ReactNode, useMemo, useState } from "react";
import { PlanProvider } from "../contexts/PlanContext.js";
import { AppProvider, useApp } from "../state/AppContext.js";
import type { SessionInfo } from "../types/protocol.js";
import type { ViewMode } from "../types/state.js";
import { ChatView } from "./ChatView.js";
import { ErrorStates } from "./ErrorStates.js";
import { InputArea } from "./InputArea.js";
import { SessionPicker } from "./SessionPicker.js";
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
  const { stdout } = useStdout();
  const [columns] = useState(stdout?.columns ?? 80);
  const [rows] = useState(stdout?.rows ?? 24);

  useInput((input, key) => {
    if (key.ctrl && input === "b") {
      const nextView: ViewMode = state.currentView === "focused" ? "split" : "focused";
      dispatch({ type: "SET_VIEW", view: nextView });
      return;
    }

      if (key.ctrl && input === "c") {
        if (state.isStreaming) {
          dispatch({ type: "SET_STREAMING", isStreaming: false });
        } else {
          process.exit(0);
      }
      return;
    }

      if (key.escape) {
        if (state.isStreaming) {
          dispatch({ type: "SET_STREAMING", isStreaming: false });
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
      <InputArea isActive={state.currentView !== "dashboard"} />
    </Box>
  );
}

export function App(): ReactNode {
  return (
    <AppProvider>
      <PlanProvider>
        <AppShell />
      </PlanProvider>
    </AppProvider>
  );
}

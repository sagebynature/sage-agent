import { Box, Text, useInput } from "ink";
import { type ReactNode, useCallback, useEffect, useRef } from "react";
import { SageClient } from "../ipc/client.js";
import { SageClientContext, useSageClient, useClientStatus } from "../ipc/hooks.js";
import { METHODS } from "../types/protocol.js";
import { BlockProvider, useBlocks } from "../state/BlockContext.js";
import { BlockEventRouter } from "../integration/BlockEventRouter.js";
import type { BlockState } from "../state/blockReducer.js";
import type { PermissionDecision } from "../types/state.js";
import { ConversationView } from "./ConversationView.js";
import { InputPrompt } from "./InputPrompt.js";
import { BottomBar } from "./BottomBar.js";
import { PermissionPrompt } from "./PermissionPrompt.js";
import { useResizeHandler } from "../hooks/useResizeHandler.js";

const NOTIFICATION_METHODS = [
  METHODS.STREAM_DELTA,
  METHODS.TOOL_STARTED,
  METHODS.TOOL_COMPLETED,
  METHODS.RUN_COMPLETED,
  METHODS.USAGE_UPDATE,
  METHODS.PERMISSION_REQUEST,
  METHODS.COMPACTION_STARTED,
  METHODS.BACKGROUND_COMPLETED,
  METHODS.DELEGATION_STARTED,
  METHODS.DELEGATION_COMPLETED,
  METHODS.ERROR,
] as const;

function AppShell(): ReactNode {
  const { state, dispatch } = useBlocks();
  const client = useSageClient();
  const connectionStatus = useClientStatus();
  const { width: columns } = useResizeHandler();
  const stateRef = useRef<BlockState>(state);
  stateRef.current = state;

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
      // Start stream immediately BEFORE the RPC so notifications aren't dropped
      const optimisticRunId = `run_${Date.now()}`;
      dispatch({ type: "STREAM_START", runId: optimisticRunId });

      try {
        await client.request(METHODS.AGENT_RUN, { message: text });
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
            try {
              await client.request("session/clear", {
                ...(stateRef.current.session?.id
                  ? { sessionId: stateRef.current.session.id }
                  : {}),
              });
            } catch { /* best effort */ }
            dispatch({ type: "CLEAR_BLOCKS" });
            result = "Conversation cleared.";
            break;
          case "reset":
          case "restart":
            try {
              await client.request("session/clear", {});
            } catch { /* best effort */ }
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
      <ConversationView
        completedBlocks={state.completedBlocks}
        activeStream={state.activeStream}
      />
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
        isActive={!state.activeStream && connectionStatus === "connected"}
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

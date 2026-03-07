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
          case "help":
            result = "Commands: /help, /model, /models, /tools, /usage, /compact, /sessions, /clear, /quit";
            break;
          case "model":
          case "models": {
            const r = await client.request("config/get", { key: "model" });
            result = `Current model: ${JSON.stringify(r, null, 2)}`;
            break;
          }
          case "tools": {
            const r = await client.request("tools/list", {});
            result = JSON.stringify(r, null, 2);
            break;
          }
          case "usage":
            result = [
              `Model: ${state.usage.model}`,
              `Prompt tokens: ${state.usage.promptTokens}`,
              `Completion tokens: ${state.usage.completionTokens}`,
              `Cost: $${state.usage.totalCost.toFixed(2)}`,
              `Context: ${state.usage.contextUsagePercent}%`,
            ].join("\n");
            break;
          case "compact": {
            const r = await client.request("agent/compact", {});
            result = JSON.stringify(r, null, 2);
            break;
          }
          case "sessions": {
            const r = await client.request("session/list", {});
            result = JSON.stringify(r, null, 2);
            break;
          }
          case "clear":
            await client.request("session/clear", {});
            dispatch({ type: "SET_SESSION", session: null });
            dispatch({ type: "CLEAR_ERROR" });
            result = "Session cleared.";
            break;
          case "quit":
          case "exit":
          case "q":
            process.exit(0);
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
    [client, dispatch, state.usage],
  );

  useInput((input, key) => {
    if (key.ctrl && input === "c") {
      if (state.activeStream) {
        void handleCancel();
      } else {
        process.exit(0);
      }
      return;
    }
    if (key.escape) {
      if (state.activeStream) {
        void handleCancel();
      } else if (state.error) {
        dispatch({ type: "CLEAR_ERROR" });
      }
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

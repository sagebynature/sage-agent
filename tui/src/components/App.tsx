import { Box, Text, useInput } from "ink";
import { type ReactNode, useCallback, useEffect, useRef } from "react";
import { SageClient } from "../ipc/client.js";
import { SageClientContext, useSageClient } from "../ipc/hooks.js";
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
  METHODS.ERROR,
] as const;

function AppShell(): ReactNode {
  const { state, dispatch } = useBlocks();
  const client = useSageClient();
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
      if (client.status !== "connected") return;

      dispatch({ type: "SUBMIT_MESSAGE", content: text });

      try {
        const result = await client.request(METHODS.AGENT_RUN, { message: text });
        const runId =
          typeof result === "object" && result !== null && "runId" in result
            ? String((result as Record<string, unknown>).runId)
            : `run_${Date.now()}`;
        dispatch({ type: "STREAM_START", runId });
      } catch (err: unknown) {
        dispatch({
          type: "SET_ERROR",
          error: err instanceof Error ? err.message : "Failed to send message",
        });
      }
    },
    [client, dispatch],
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
    async (id: string, decision: PermissionDecision) => {
      dispatch({ type: "PERMISSION_RESPOND", id, decision });
      try {
        await client.request(METHODS.PERMISSION_RESPOND, {
          request_id: id,
          decision,
        });
      } catch {
        // Best effort
      }
    },
    [client, dispatch],
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
          <Text dimColor>{" (ESC to dismiss)"}</Text>
        </Box>
      )}
      {pendingPermissions.map((perm) => (
        <PermissionPrompt
          key={perm.id}
          request={perm}
          onRespond={handlePermissionRespond}
        />
      ))}
      <InputPrompt onSubmit={handleSubmit} isActive={!state.activeStream} />
      <BottomBar usage={state.usage} />
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

import type { Dispatch } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { BlockEventRouter } from "../integration/BlockEventRouter.js";
import type { BlockAction } from "../state/blockReducer.js";
import { METHODS } from "../types/protocol.js";
import { SageClient } from "../ipc/client.js";

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

function useBatchedDispatch(dispatch: Dispatch<BlockAction>): (action: BlockAction) => void {
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

export function useAppBootstrap(
  client: SageClient,
  dispatch: Dispatch<BlockAction>,
): {
  mainAgentName: string;
  configuredModel: string;
} {
  const [mainAgentName, setMainAgentName] = useState("");
  const [configuredModel, setConfiguredModel] = useState("");
  const batchedDispatch = useBatchedDispatch(dispatch);

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
  }, [batchedDispatch, client, dispatch]);

  return { mainAgentName, configuredModel };
}

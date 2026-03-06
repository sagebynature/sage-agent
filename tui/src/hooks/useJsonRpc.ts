import { useCallback, useEffect, useRef } from "react";
import { useSageClient, useClientStatus } from "../ipc/hooks.js";

type NotificationHandler = (params: Record<string, unknown>) => void;

export function useJsonRpc() {
  const client = useSageClient();
  const status = useClientStatus();
  const unsubscribersRef = useRef<Array<() => void>>([]);

  useEffect(() => {
    return () => {
      for (const unsubscribe of unsubscribersRef.current) {
        unsubscribe();
      }
      unsubscribersRef.current = [];
    };
  }, []);

  const send = useCallback(
    async <T = unknown>(
      method: string,
      params?: Record<string, unknown>,
    ): Promise<T> => {
      return client.request<T>(method, params);
    },
    [client],
  );

  const subscribe = useCallback(
    (method: string, handler: NotificationHandler): (() => void) => {
      const unsubscribe = client.onNotification(method, handler);
      unsubscribersRef.current.push(unsubscribe);

      return () => {
        unsubscribe();
        unsubscribersRef.current = unsubscribersRef.current.filter(
          (entry) => entry !== unsubscribe,
        );
      };
    },
    [client],
  );

  return {
    send,
    subscribe,
    isConnected: status === "connected",
    status,
  };
}

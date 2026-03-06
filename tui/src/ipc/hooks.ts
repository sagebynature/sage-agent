import {
  createContext,
  use,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type { SageClient } from "./client.js";
import type { ClientStatus, NotificationHandler } from "./types.js";

const SageClientContext = createContext<SageClient | null>(null);

export { SageClientContext };

export function useSageClient(): SageClient {
  const client = use(SageClientContext);
  if (!client) {
    throw new Error("useSageClient must be used within SageClientProvider");
  }
  return client;
}

export function useNotification(
  method: string,
  callback: NotificationHandler,
): void {
  const client = useSageClient();
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    const handler: NotificationHandler = (params) => callbackRef.current(params);
    return client.onNotification(method, handler);
  }, [client, method]);
}

export function useRequest<T = unknown>(method: string): [
  (params?: Record<string, unknown>) => Promise<T>,
  { loading: boolean; error: Error | null; data: T | null },
] {
  const client = useSageClient();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<T | null>(null);

  const execute = useCallback(
    async (params?: Record<string, unknown>) => {
      setLoading(true);
      setError(null);

      try {
        const result = await client.request<T>(method, params);
        setData(result);
        return result;
      } catch (err) {
        const requestError =
          err instanceof Error ? err : new Error(String(err));
        setError(requestError);
        throw requestError;
      } finally {
        setLoading(false);
      }
    },
    [client, method],
  );

  return [execute, { loading, error, data }];
}

export function useClientStatus(): ClientStatus {
  const client = useSageClient();
  const [status, setStatus] = useState<ClientStatus>(client.status);

  useEffect(() => {
    const onConnect = () => setStatus("connected");
    const onDisconnect = () => setStatus("disconnected");
    const onError = () => setStatus("error");

    client.on("connected", onConnect);
    client.on("disconnected", onDisconnect);
    client.on("error", onError);

    return () => {
      client.off("connected", onConnect);
      client.off("disconnected", onDisconnect);
      client.off("error", onError);
    };
  }, [client]);

  return status;
}

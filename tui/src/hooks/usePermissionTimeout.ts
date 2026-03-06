import { useEffect, useMemo, useState } from "react";

export const PERMISSION_TIMEOUT_EVENT = "sage:permission-timeout";

export interface PermissionTimeoutAction {
  type: "PERMISSION_RESPOND";
  id: string;
  decision: "deny";
}

export interface PermissionTimeoutState {
  timeRemaining: number;
  isExpired: boolean;
}

export function usePermissionTimeout(
  requestId: string,
  timeout = 60_000,
): PermissionTimeoutState {
  const [timeRemaining, setTimeRemaining] = useState(timeout);
  const [isExpired, setIsExpired] = useState(false);

  useEffect(() => {
    setTimeRemaining(timeout);
    setIsExpired(false);

    if (!requestId) {
      return;
    }

    const interval = setInterval(() => {
      setTimeRemaining((prev) => Math.max(0, prev - 1000));
    }, 1000);

    const timer = setTimeout(() => {
      const action: PermissionTimeoutAction = {
        type: "PERMISSION_RESPOND",
        id: requestId,
        decision: "deny",
      };
      process.emit(PERMISSION_TIMEOUT_EVENT, action);
      setIsExpired(true);
      setTimeRemaining(0);
    }, timeout);

    return () => {
      clearInterval(interval);
      clearTimeout(timer);
    };
  }, [requestId, timeout]);

  const normalizedTimeRemaining = useMemo(() => {
    return Math.max(0, timeRemaining);
  }, [timeRemaining]);

  return {
    timeRemaining: normalizedTimeRemaining,
    isExpired,
  };
}

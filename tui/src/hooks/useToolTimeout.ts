import { useEffect, useMemo, useState } from "react";

export const TOOL_TIMEOUT_EVENT = "sage:tool-timeout";

export interface ToolTimeoutAction {
  type: "TOOL_TIMEOUT";
  callId: string;
  message: string;
}

export interface UseToolTimeoutState {
  isTimedOut: boolean;
  statusMessage: string;
}

export function createToolTimeoutAction(callId: string): ToolTimeoutAction {
  return {
    type: "TOOL_TIMEOUT",
    callId,
    message: "Tool interrupted — no response after 30s",
  };
}

export function useToolTimeout(
  toolCallId: string,
  timeout = 30_000,
): UseToolTimeoutState {
  const [isTimedOut, setIsTimedOut] = useState(false);

  useEffect(() => {
    setIsTimedOut(false);

    if (!toolCallId) {
      return;
    }

    const timer = setTimeout(() => {
      const action = createToolTimeoutAction(toolCallId);
      process.emit(TOOL_TIMEOUT_EVENT, action);
      setIsTimedOut(true);
    }, timeout);

    return () => {
      clearTimeout(timer);
    };
  }, [toolCallId, timeout]);

  const statusMessage = useMemo(() => {
    if (!isTimedOut) {
      return "";
    }

    return "Tool interrupted — no response after 30s";
  }, [isTimedOut]);

  return {
    isTimedOut,
    statusMessage,
  };
}

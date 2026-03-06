import { useEffect, useState } from "react";

export const CONTEXT_ERROR_EVENT = "sage:error";

const EXHAUSTION_OPTIONS = ["compact history", "start new session"];

export interface ContextExhaustionState {
  isExhausted: boolean;
  options: string[];
}

export function isContextExhaustionError(error: unknown): boolean {
  if (typeof error !== "object" || error === null) {
    return false;
  }

  const payload = error as Record<string, unknown>;

  if (payload.type === "token_exhaustion" || payload.type === "context_full") {
    return true;
  }

  const code = payload.code;
  if (typeof code === "string" && code.toLowerCase().includes("token_exhaustion")) {
    return true;
  }

  const message = payload.message;
  if (typeof message !== "string") {
    return false;
  }

  const normalized = message.toLowerCase();
  return normalized.includes("context length exceeded");
}

export function useContextExhaustion(): ContextExhaustionState {
  const [isExhausted, setIsExhausted] = useState(false);

  useEffect(() => {
    const onError = (error: unknown) => {
      if (isContextExhaustionError(error)) {
        setIsExhausted(true);
      }
    };

    process.on(CONTEXT_ERROR_EVENT, onError);
    return () => {
      process.off(CONTEXT_ERROR_EVENT, onError);
    };
  }, []);

  return {
    isExhausted,
    options: EXHAUSTION_OPTIONS,
  };
}

import { useCallback, useState } from "react";

export interface RetryState {
  retryAfter: number;
  attempt: number;
  isRetrying: boolean;
  retry: () => void;
  cancel: () => void;
}

export function isRateLimitError(error: unknown): boolean {
  if (typeof error !== "object" || error === null) {
    return false;
  }

  const payload = error as Record<string, unknown>;
  if (payload.type === "rate_limit") {
    return true;
  }

  const code = payload.code;
  if (typeof code === "string" && code.toLowerCase().includes("rate_limit")) {
    return true;
  }

  const message = payload.message;
  if (typeof message === "string" && message.toLowerCase().includes("rate limit")) {
    return true;
  }

  return false;
}

export function getBackoffDelaySeconds(
  attempt: number,
  randomValue = Math.random(),
): number {
  const base = Math.min(2 ** Math.max(0, attempt - 1), 30);
  const jitterRange = base * 0.2;
  const jitter = (randomValue * 2 - 1) * jitterRange;
  const jittered = base + jitter;
  return Math.max(0, Math.min(30, jittered));
}

export function useRetryWithBackoff(): RetryState {
  const [attempt, setAttempt] = useState(0);
  const [retryAfter, setRetryAfter] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);

  const retry = useCallback(() => {
    setAttempt((prev) => {
      const nextAttempt = prev + 1;
      const delay = getBackoffDelaySeconds(nextAttempt);
      setRetryAfter(delay);
      setIsRetrying(true);
      return nextAttempt;
    });
  }, []);

  const cancel = useCallback(() => {
    setAttempt(0);
    setRetryAfter(0);
    setIsRetrying(false);
  }, []);

  return {
    retryAfter,
    attempt,
    isRetrying,
    retry,
    cancel,
  };
}

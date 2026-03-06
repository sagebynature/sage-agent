import { useCallback, useMemo, useRef, useState } from "react";

export interface MessageQueueState {
  queue: string[];
  enqueue: (msg: string) => void;
  flush: () => string | undefined;
  indicator: string;
}

export function useMessageQueue(): MessageQueueState {
  const queueRef = useRef<string[]>([]);
  const [queue, setQueue] = useState<string[]>([]);

  const enqueue = useCallback((msg: string) => {
    queueRef.current = [...queueRef.current, msg];
    setQueue(queueRef.current);
  }, []);

  const flush = useCallback(() => {
    const [head, ...rest] = queueRef.current;
    queueRef.current = rest;
    setQueue(rest);
    return head;
  }, []);

  const indicator = useMemo(() => {
    if (queue.length === 0) {
      return "";
    }

    return "Message queued — waiting for response";
  }, [queue.length]);

  return {
    queue,
    enqueue,
    flush,
    indicator,
  };
}

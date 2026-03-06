import { createElement, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { StreamDeltaPayload } from "../types/protocol.js";
import { MarkdownRenderer } from "../renderer/MarkdownRenderer.js";

const FRAME_DEBOUNCE_MS = 16;

export interface UseMarkdownStreamResult {
  rendered: ReactNode;
  isStreaming: boolean;
  rawText: string;
  pushChunk: (chunk: string | StreamDeltaPayload) => void;
  setStreaming: (value: boolean) => void;
  reset: (nextText?: string) => void;
}

function getChunkDelta(chunk: string | StreamDeltaPayload): string {
  if (typeof chunk === "string") {
    return chunk;
  }

  return chunk.delta;
}

export function useMarkdownStream(initialText = ""): UseMarkdownStreamResult {
  const [rawText, setRawText] = useState(initialText);
  const [debouncedText, setDebouncedText] = useState(initialText);
  const [isStreaming, setIsStreaming] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    timerRef.current = setTimeout(() => {
      setDebouncedText(rawText);
      timerRef.current = undefined;
    }, FRAME_DEBOUNCE_MS);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = undefined;
      }
    };
  }, [rawText]);

  const pushChunk = useCallback((chunk: string | StreamDeltaPayload) => {
    const delta = getChunkDelta(chunk);
    if (!delta) {
      return;
    }

    setRawText((prev) => `${prev}${delta}`);
    setIsStreaming(true);
  }, []);

  const setStreaming = useCallback((value: boolean) => {
    setIsStreaming(value);
  }, []);

  const reset = useCallback((nextText = "") => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = undefined;
    }

    setRawText(nextText);
    setDebouncedText(nextText);
    setIsStreaming(false);
  }, []);

  const rendered = useMemo<ReactNode>(
    () => createElement(MarkdownRenderer, { content: debouncedText, isStreaming }),
    [debouncedText, isStreaming],
  );

  return {
    rendered,
    isStreaming,
    rawText,
    pushChunk,
    setStreaming,
    reset,
  };
}

export { FRAME_DEBOUNCE_MS };

import { Box, Text } from "ink";
import { createElement, createRef, isValidElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { StreamDeltaPayload } from "../../types/protocol.js";
import { renderApp } from "../../test-utils.js";
import { FRAME_DEBOUNCE_MS, useMarkdownStream, type UseMarkdownStreamResult } from "../useMarkdownStream.js";

interface HookHarnessProps {
  initialText?: string;
  streamRef: React.RefObject<UseMarkdownStreamResult | null>;
}

function HookHarness({ initialText = "", streamRef }: HookHarnessProps): ReactNode {
  const stream = useMarkdownStream(initialText);
  streamRef.current = stream;

  return createElement(
    Box,
    { flexDirection: "column" },
    createElement(Text, null, `raw-len:${stream.rawText.length}`),
    createElement(Text, null, `streaming:${String(stream.isStreaming)}`),
    createElement(Box, null, stream.rendered),
  );
}

function getRenderedMarkdownContent(streamRef: React.RefObject<UseMarkdownStreamResult | null>): string {
  const rendered = streamRef.current?.rendered;
  if (!isValidElement<{ content: string }>(rendered)) {
    throw new Error("Expected rendered to be a React element");
  }

  return rendered.props.content;
}

describe("useMarkdownStream", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns initial state", () => {
    const streamRef = createRef<UseMarkdownStreamResult | null>();
    const { lastFrame } = renderApp(createElement(HookHarness, { streamRef, initialText: "seed" }));

    expect(streamRef.current?.rawText).toBe("seed");
    expect(streamRef.current?.isStreaming).toBe(false);
    expect(lastFrame()).toContain("raw-len:4");
  });

  it("pushChunk accumulates text and enables streaming", async () => {
    const streamRef = createRef<UseMarkdownStreamResult | null>();
    renderApp(createElement(HookHarness, { streamRef }));

    streamRef.current?.pushChunk("Hello");
    await vi.advanceTimersByTimeAsync(FRAME_DEBOUNCE_MS + 1);

    expect(streamRef.current?.rawText).toBe("Hello");
    expect(streamRef.current?.isStreaming).toBe(true);
  });

  it("supports StreamDeltaPayload chunks", async () => {
    const streamRef = createRef<UseMarkdownStreamResult | null>();
    renderApp(createElement(HookHarness, { streamRef }));

    const payload: StreamDeltaPayload = { delta: " world", turn: 1 };
    streamRef.current?.pushChunk("hello");
    streamRef.current?.pushChunk(payload);
    await vi.advanceTimersByTimeAsync(FRAME_DEBOUNCE_MS + 1);

    expect(streamRef.current?.rawText).toBe("hello world");
  });

  it("debounces rendered updates", async () => {
    const streamRef = createRef<UseMarkdownStreamResult | null>();
    renderApp(createElement(HookHarness, { streamRef }));

    streamRef.current?.pushChunk("# Debounced");
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(FRAME_DEBOUNCE_MS - 1);
    expect(getRenderedMarkdownContent(streamRef)).toBe("");

    await vi.advanceTimersByTimeAsync(2);
    expect(getRenderedMarkdownContent(streamRef)).toBe("# Debounced");
  });

  it("re-renders from the full accumulated text", async () => {
    const streamRef = createRef<UseMarkdownStreamResult | null>();
    renderApp(createElement(HookHarness, { streamRef }));

    streamRef.current?.pushChunk("**bo");
    streamRef.current?.pushChunk("ld** and normal");
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(FRAME_DEBOUNCE_MS + 1);

    expect(getRenderedMarkdownContent(streamRef)).toBe("**bold** and normal");
  });

  it("setStreaming toggles streaming state", async () => {
    const streamRef = createRef<UseMarkdownStreamResult | null>();
    renderApp(createElement(HookHarness, { streamRef }));

    streamRef.current?.setStreaming(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(streamRef.current?.isStreaming).toBe(true);

    streamRef.current?.setStreaming(false);
    await vi.advanceTimersByTimeAsync(0);
    expect(streamRef.current?.isStreaming).toBe(false);
  });

  it("reset clears content and stops streaming", async () => {
    const streamRef = createRef<UseMarkdownStreamResult | null>();
    const { lastFrame } = renderApp(createElement(HookHarness, { streamRef }));

    streamRef.current?.pushChunk("temp");
    await vi.advanceTimersByTimeAsync(FRAME_DEBOUNCE_MS + 1);
    streamRef.current?.reset();
    await vi.advanceTimersByTimeAsync(0);

    expect(streamRef.current?.rawText).toBe("");
    expect(streamRef.current?.isStreaming).toBe(false);
    expect(lastFrame()).toContain("raw-len:0");
  });
});

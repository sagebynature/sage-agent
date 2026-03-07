import { Box, Text } from "ink";
import { type ReactNode, useEffect, useRef, useState } from "react";
import type { ActiveStream } from "../types/blocks.js";
import { renderMarkdown } from "../renderer/MarkdownRenderer.js";

const FRAME_DEBOUNCE_MS = 16;
const ELAPSED_INTERVAL_MS = 1000;
const SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
const SPINNER_INTERVAL_MS = 80;

interface ActiveStreamViewProps {
  stream: ActiveStream | null;
}

function useElapsedTimer(startedAt: number | null): string {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (startedAt === null) return;

    setElapsed(Math.floor((Date.now() - startedAt) / 1000));

    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, ELAPSED_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [startedAt]);

  if (elapsed < 60) return `${elapsed}s`;
  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  return `${min}m ${sec}s`;
}

function useSpinner(): string {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setFrame((prev) => (prev + 1) % SPINNER_FRAMES.length);
    }, SPINNER_INTERVAL_MS);

    return () => clearInterval(interval);
  }, []);

  return SPINNER_FRAMES[frame]!;
}

function formatToolArgs(args: Record<string, unknown>): string {
  if (args.path) return ` ${args.path}`;
  if (args.file_path) return ` ${args.file_path}`;
  if (args.command) return ` ${args.command}`;
  if (args.pattern) return ` ${args.pattern}`;
  if (args.url) return ` ${args.url}`;
  return "";
}

function useDebouncedMarkdown(content: string, isStreaming: boolean): string {
  const [rendered, setRendered] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    timerRef.current = setTimeout(() => {
      setRendered(renderMarkdown(content, isStreaming));
      timerRef.current = undefined;
    }, FRAME_DEBOUNCE_MS);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = undefined;
      }
    };
  }, [content, isStreaming]);

  return rendered;
}

function ThinkingIndicator({ startedAt }: { startedAt: number }): ReactNode {
  const elapsed = useElapsedTimer(startedAt);
  const spinner = useSpinner();

  return (
    <Box>
      <Text color="cyan">{spinner} Thinking...</Text>
      <Text dimColor>{" ("}{elapsed}{")"}</Text>
    </Box>
  );
}

export function ActiveStreamView({ stream }: ActiveStreamViewProps): ReactNode {
  if (!stream) return null;

  const runningTools = stream.tools.filter((t) => t.status === "running");
  const rendered = useDebouncedMarkdown(stream.content, true);

  return (
    <Box flexDirection="column">
      {runningTools.map((tool) => (
        <Text key={tool.callId}>
          {"● "}{tool.name}{formatToolArgs(tool.arguments)}
          <Text dimColor>{"  ... running"}</Text>
        </Text>
      ))}
      {stream.isThinking ? (
        <ThinkingIndicator startedAt={stream.startedAt} />
      ) : stream.content.length > 0 ? (
        <Box flexDirection="column">
          <Text>{"● "}{rendered}</Text>
        </Box>
      ) : null}
    </Box>
  );
}

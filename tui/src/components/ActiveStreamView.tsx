import { Box, Text } from "ink";
import { type ReactNode, useEffect, useRef, useState } from "react";
import type { ActiveStream } from "../types/blocks.js";
import { renderMarkdown } from "../renderer/MarkdownRenderer.js";

const FRAME_DEBOUNCE_MS = 16;

interface ActiveStreamViewProps {
  stream: ActiveStream | null;
}

function formatElapsed(startedAt: number): string {
  const elapsed = Math.floor((Date.now() - startedAt) / 1000);
  if (elapsed < 60) return `${elapsed}s`;
  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  return `${min}m ${sec}s`;
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
        <Box>
          <Text color="cyan">{"✻ Thinking..."}</Text>
          <Text dimColor>{" ("}{formatElapsed(stream.startedAt)}{")"}</Text>
        </Box>
      ) : stream.content.length > 0 ? (
        <Box flexDirection="column">
          <Text>{"● "}{rendered}</Text>
        </Box>
      ) : null}
    </Box>
  );
}

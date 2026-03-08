import { Box, Text } from "ink";
import { createContext, type ReactNode, useContext, useEffect, useState } from "react";
import type { ActiveStream } from "../types/blocks.js";
import { formatToolLabel, formatToolResultPreview } from "../utils/tool-format.js";

const ELAPSED_INTERVAL_MS = 1000;
const SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
const SPINNER_INTERVAL_MS = 80;

interface ActiveStreamViewProps {
  stream: ActiveStream | null;
}

// Shared spinner context — single timer drives all spinners to prevent flickering.
const SpinnerContext = createContext("⠋");

function SpinnerProvider({ children }: { children: ReactNode }): ReactNode {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setFrame((prev) => (prev + 1) % SPINNER_FRAMES.length);
    }, SPINNER_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  return (
    <SpinnerContext value={SPINNER_FRAMES[frame]!}>
      {children}
    </SpinnerContext>
  );
}

function useSpinner(): string {
  return useContext(SpinnerContext);
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

interface ToolInfo {
  status: string;
  name: string;
  arguments: Record<string, unknown>;
  durationMs?: number;
  error?: string;
}

function RunningToolIndicator({ tool }: { tool: ToolInfo }): ReactNode {
  const spinner = useSpinner();
  const label = formatToolLabel(tool.name, tool.arguments);
  const isDelegate = tool.name.startsWith("delegate");
  const color = isDelegate ? "magenta" : "blue";

  return (
    <Text>
      <Text color={color}>{spinner} {label}</Text>
    </Text>
  );
}

function ToolStatusIndicator({ tool }: { tool: ToolInfo }): ReactNode {
  const label = formatToolLabel(tool.name, tool.arguments);
  const resultPreview = formatToolResultPreview(tool);
  switch (tool.status) {
    case "running":
      return <Box><RunningToolIndicator tool={tool} /></Box>;
    case "completed":
      return (
        <Box flexDirection="column">
          <Text dimColor>
            {"✓ "}{label}
            {tool.durationMs !== undefined ? `  ${tool.durationMs < 1000 ? `${tool.durationMs}ms` : `${(tool.durationMs / 1000).toFixed(1)}s`}` : ""}
          </Text>
          {resultPreview && (
            <Text dimColor>{"  -> "}{resultPreview}</Text>
          )}
        </Box>
      );
    case "failed":
      return (
        <Box flexDirection="column">
          <Text>
            <Text color="red">{"✗ "}{label}</Text>
            {tool.error ? <Text dimColor>{"  "}{tool.error}</Text> : null}
          </Text>
          {resultPreview && (
            <Text dimColor>{"  -> "}{resultPreview}</Text>
          )}
        </Box>
      );
    default:
      return null;
  }
}

const MAX_VISIBLE_STREAM_LINES = 30;

export function truncateStreamLines(
  content: string,
  maxLines: number,
): { lines: string[]; truncatedCount: number } {
  const allLines = content.split("\n");
  if (allLines.length <= maxLines) {
    return { lines: allLines, truncatedCount: 0 };
  }
  const truncatedCount = allLines.length - maxLines;
  return { lines: allLines.slice(-maxLines), truncatedCount };
}

function StreamContent({ content }: { content: string }): ReactNode {
  const { lines, truncatedCount } = truncateStreamLines(content, MAX_VISIBLE_STREAM_LINES);
  return (
    <Box flexDirection="column">
      {truncatedCount > 0 && (
        <Text dimColor>{"  ... ("}{truncatedCount + lines.length}{" lines, showing last "}{lines.length}{")"}</Text>
      )}
      {lines.map((line, i) => (
        <Text key={i}>{i === 0 && truncatedCount === 0 ? `● ${line}` : `  ${line}`}</Text>
      ))}
    </Box>
  );
}

export function ActiveStreamView({ stream }: ActiveStreamViewProps): ReactNode {
  if (!stream) return null;

  const hasTools = stream.tools.length > 0;
  const hasRunningTools = stream.tools.some((t) => t.status === "running");

  return (
    <Box flexDirection="column">
      {hasRunningTools ? (
        <SpinnerProvider>
          {stream.tools.map((tool, idx) => (
            <ToolStatusIndicator key={`${idx}_${tool.callId}`} tool={tool} />
          ))}
        </SpinnerProvider>
      ) : (
        stream.tools.map((tool, idx) => (
          <ToolStatusIndicator key={`${idx}_${tool.callId}`} tool={tool} />
        ))
      )}
      {stream.isThinking && !hasTools ? (
        <SpinnerProvider>
          <ThinkingIndicator startedAt={stream.startedAt} />
        </SpinnerProvider>
      ) : stream.content.length > 0 ? (
        <StreamContent content={stream.content} />
      ) : null}
    </Box>
  );
}

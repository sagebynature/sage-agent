import { Box, Text } from "ink";
import { createContext, type ReactNode, useContext, useEffect, useState } from "react";
import type { ActiveStream } from "../types/blocks.js";
import { detectCapabilities, type TerminalCapabilities } from "../utils/terminal.js";
import { formatToolLabel, formatToolResultPreview } from "../utils/tool-format.js";

const ELAPSED_INTERVAL_MS = 1000;
const SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
const SPINNER_INTERVAL_MS = 80;
const ACTIVE_STATUS_PALETTE = [
  { color: "#7fe7ff", bold: true },
  { color: "#4dcfff", bold: false },
  { color: "#2f9bff", bold: false },
] as const;
const DELEGATE_STATUS_PALETTE = [
  { color: "#ff8cf6", bold: true },
  { color: "#ff5fe0", bold: false },
  { color: "#d948ff", bold: false },
] as const;
const STATIC_ACTIVE_STYLE = { color: "cyan", bold: false } as const;
const STATIC_DELEGATE_STYLE = { color: "magenta", bold: false } as const;

interface ActiveStreamViewProps {
  stream: ActiveStream | null;
}

// Shared spinner context — single timer drives all spinners to prevent flickering.
interface ActiveAnimationState {
  spinner: string;
  phase: number;
  colorDepth: TerminalCapabilities["colorDepth"];
}

const SpinnerContext = createContext<ActiveAnimationState>({
  spinner: SPINNER_FRAMES[0]!,
  phase: 0,
  colorDepth: 16,
});

function SpinnerProvider({
  children,
  colorDepth,
}: {
  children: ReactNode;
  colorDepth: TerminalCapabilities["colorDepth"];
}): ReactNode {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setFrame((prev) => (prev + 1) % SPINNER_FRAMES.length);
    }, SPINNER_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  return (
    <SpinnerContext
      value={{
        spinner: SPINNER_FRAMES[frame]!,
        phase: frame % ACTIVE_STATUS_PALETTE.length,
        colorDepth,
      }}
    >
      {children}
    </SpinnerContext>
  );
}

function useActiveAnimation(): ActiveAnimationState {
  return useContext(SpinnerContext);
}

export function resolveActiveStatusStyle(
  phase: number,
  isDelegate: boolean,
  colorDepth: TerminalCapabilities["colorDepth"],
): { color: string; bold: boolean } {
  if (colorDepth !== 24) {
    return isDelegate ? STATIC_DELEGATE_STYLE : STATIC_ACTIVE_STYLE;
  }

  const palette = isDelegate ? DELEGATE_STATUS_PALETTE : ACTIVE_STATUS_PALETTE;
  return palette[phase % palette.length]!;
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
  const { spinner, phase, colorDepth } = useActiveAnimation();
  const style = resolveActiveStatusStyle(phase, false, colorDepth);

  return (
    <Box>
      <Text color={style.color} bold={style.bold}>{spinner} Thinking...</Text>
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
  const { spinner, phase, colorDepth } = useActiveAnimation();
  const label = formatToolLabel(tool.name, tool.arguments);
  const isDelegate = tool.name.startsWith("delegate");
  const style = resolveActiveStatusStyle(phase, isDelegate, colorDepth);

  return (
    <Text>
      <Text color={style.color} bold={style.bold}>{spinner} {label}</Text>
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
  const colorDepth = detectCapabilities().colorDepth;

  return (
    <Box flexDirection="column">
      {hasRunningTools ? (
        <SpinnerProvider colorDepth={colorDepth}>
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
        <SpinnerProvider colorDepth={colorDepth}>
          <ThinkingIndicator startedAt={stream.startedAt} />
        </SpinnerProvider>
      ) : stream.content.length > 0 ? (
        <StreamContent content={stream.content} />
      ) : null}
    </Box>
  );
}

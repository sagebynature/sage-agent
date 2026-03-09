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
const ACTIVE_IDLE_COLOR = "#5c6977";
const DELEGATE_IDLE_COLOR = "#796275";
const STATIC_ACTIVE_STYLE = { color: "cyan", bold: false } as const;
const STATIC_DELEGATE_STYLE = { color: "magenta", bold: false } as const;

interface ActiveStreamViewProps {
  stream: ActiveStream | null;
}

// Shared spinner context — single timer drives all spinners to prevent flickering.
interface ActiveAnimationState {
  spinner: string;
  frame: number;
  colorDepth: TerminalCapabilities["colorDepth"];
}

const SpinnerContext = createContext<ActiveAnimationState>({
  spinner: SPINNER_FRAMES[0]!,
  frame: 0,
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
        frame,
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
  isDelegate: boolean,
  colorDepth: TerminalCapabilities["colorDepth"],
): { color: string; bold: boolean } {
  if (colorDepth !== 24) {
    return isDelegate ? STATIC_DELEGATE_STYLE : STATIC_ACTIVE_STYLE;
  }

  return isDelegate ? DELEGATE_STATUS_PALETTE[0]! : ACTIVE_STATUS_PALETTE[0]!;
}

interface ActiveLabelStyle {
  char: string;
  color: string;
  bold: boolean;
  dimColor: boolean;
  inverse: boolean;
}

export function resolveSweepPosition(frame: number, textLength: number): number {
  if (textLength <= 1) {
    return 0;
  }

  const max = textLength - 1;
  const period = max * 2;
  const offset = frame % period;
  return offset <= max ? offset : period - offset;
}

export function resolveActiveLabelStyles(
  text: string,
  frame: number,
  isDelegate: boolean,
  colorDepth: TerminalCapabilities["colorDepth"],
): ActiveLabelStyle[] {
  const chars = [...text];
  const staticStyle = isDelegate ? STATIC_DELEGATE_STYLE : STATIC_ACTIVE_STYLE;

  if (colorDepth !== 24) {
    return chars.map((char) => ({
      char,
      color: staticStyle.color,
      bold: staticStyle.bold,
      dimColor: false,
      inverse: false,
    }));
  }

  const center = resolveSweepPosition(frame, chars.length);
  const palette = isDelegate ? DELEGATE_STATUS_PALETTE : ACTIVE_STATUS_PALETTE;
  const idleColor = isDelegate ? DELEGATE_IDLE_COLOR : ACTIVE_IDLE_COLOR;

  return chars.map((char, index) => {
    const distance = Math.abs(index - center);

    if (distance === 0) {
      return { char, color: palette[0]!.color, bold: true, dimColor: false, inverse: false };
    }
    if (distance === 1) {
      return { char, color: palette[1]!.color, bold: true, dimColor: false, inverse: false };
    }
    if (distance === 2) {
      return { char, color: palette[2]!.color, bold: false, dimColor: false, inverse: false };
    }

    return { char, color: idleColor, bold: false, dimColor: true, inverse: false };
  });
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
  const { spinner, colorDepth } = useActiveAnimation();
  const style = resolveActiveStatusStyle(false, colorDepth);

  return (
    <Box>
      <Text color={style.color} bold={style.bold}>{spinner} </Text>
      <AnimatedActiveLabel text="Thinking..." isDelegate={false} />
      <Text dimColor>{" ("}{elapsed}{")"}</Text>
    </Box>
  );
}

function ComplexityBadge({
  score,
  level,
}: {
  score: number;
  level: "simple" | "medium" | "complex";
}): ReactNode {
  return <Text dimColor>{`Complexity C${score} ${level}`}</Text>;
}

interface ToolInfo {
  status: string;
  name: string;
  arguments: Record<string, unknown>;
  durationMs?: number;
  error?: string;
}

function RunningToolIndicator({ tool }: { tool: ToolInfo }): ReactNode {
  const { spinner, colorDepth } = useActiveAnimation();
  const label = formatToolLabel(tool.name, tool.arguments);
  const isDelegate = tool.name.startsWith("delegate");
  const style = resolveActiveStatusStyle(isDelegate, colorDepth);

  return (
    <Text>
      <Text color={style.color} bold={style.bold}>{spinner} </Text>
      <AnimatedActiveLabel text={label} isDelegate={isDelegate} />
    </Text>
  );
}

function AnimatedActiveLabel({
  text,
  isDelegate,
}: {
  text: string;
  isDelegate: boolean;
}): ReactNode {
  const { frame, colorDepth } = useActiveAnimation();
  const chars = resolveActiveLabelStyles(text, frame, isDelegate, colorDepth);

  return (
    <Text>
      {chars.map((charStyle, index) => (
        <Text
          key={`${index}_${charStyle.char}`}
          color={charStyle.color}
          bold={charStyle.bold}
          dimColor={charStyle.dimColor}
          inverse={charStyle.inverse}
        >
          {charStyle.char}
        </Text>
      ))}
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
          <Box flexDirection="column">
            <ThinkingIndicator startedAt={stream.startedAt} />
            {stream.complexity ? (
              <ComplexityBadge
                score={stream.complexity.score}
                level={stream.complexity.level}
              />
            ) : null}
          </Box>
        </SpinnerProvider>
      ) : stream.content.length > 0 ? (
        <StreamContent content={stream.content} />
      ) : null}
    </Box>
  );
}

import { Box, Text } from "ink";
import { createContext, type ReactNode, useContext, useEffect, useState } from "react";
import type { ActiveStream } from "../types/blocks.js";

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

function formatToolArgs(args: Record<string, unknown>): string {
  if (args.path) return ` ${args.path}`;
  if (args.file_path) return ` ${args.file_path}`;
  if (args.command) return ` ${args.command}`;
  if (args.pattern) return ` ${args.pattern}`;
  if (args.url) return ` ${args.url}`;
  return "";
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
  const args = formatToolArgs(tool.arguments);
  const isDelegate = tool.name.startsWith("delegate");
  const color = isDelegate ? "magenta" : "blue";

  return (
    <Text>
      <Text color={color}>{spinner} {tool.name}</Text>
      <Text dimColor>{args}</Text>
    </Text>
  );
}

function ToolStatusIndicator({ tool }: { tool: ToolInfo }): ReactNode {
  const args = formatToolArgs(tool.arguments);
  switch (tool.status) {
    case "running":
      return <RunningToolIndicator tool={tool} />;
    case "completed":
      return (
        <Text dimColor>
          {"✓ "}{tool.name}{args}
          {tool.durationMs !== undefined ? `  ${tool.durationMs < 1000 ? `${tool.durationMs}ms` : `${(tool.durationMs / 1000).toFixed(1)}s`}` : ""}
        </Text>
      );
    case "failed":
      return (
        <Text>
          <Text color="red">{"✗ "}{tool.name}</Text>
          <Text dimColor>{args}{"  "}{tool.error ?? "failed"}</Text>
        </Text>
      );
    default:
      return null;
  }
}

function StreamContent({ content }: { content: string }): ReactNode {
  const lines = content.split("\n");
  return (
    <Box flexDirection="column">
      {lines.map((line, i) => (
        <Text key={i}>{i === 0 ? `● ${line}` : `  ${line}`}</Text>
      ))}
    </Box>
  );
}

export function ActiveStreamView({ stream }: ActiveStreamViewProps): ReactNode {
  if (!stream) return null;

  const hasTools = stream.tools.length > 0;

  return (
    <SpinnerProvider>
      <Box flexDirection="column">
        {stream.tools.map((tool, idx) => (
          <ToolStatusIndicator key={`${idx}_${tool.callId}`} tool={tool} />
        ))}
        {stream.isThinking && !hasTools ? (
          <ThinkingIndicator startedAt={stream.startedAt} />
        ) : stream.content.length > 0 ? (
          <StreamContent content={stream.content} />
        ) : null}
      </Box>
    </SpinnerProvider>
  );
}

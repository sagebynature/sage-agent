import { Box, Text } from "ink";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { useApp } from "../state/AppContext.js";
import type { AppState } from "../types/state.js";
import { COLORS } from "../theme/colors.js";

type AppMode = "idle" | "streaming" | "tool" | "permission" | "error";
const STATUSBAR_DEBOUNCE_MS = 100;

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(() => {
      setDebouncedValue(value);
      timeoutRef.current = null;
    }, delayMs);

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [value, delayMs]);

  return debouncedValue;
}

function getAppMode(state: AppState): AppMode {
  if (state.error) return "error";
  if (state.permissions.some(p => p.status === "pending")) return "permission";
  if (state.tools.some(t => t.status === "running")) return "tool";
  if (state.isStreaming) return "streaming";
  return "idle";
}

function getModeColor(mode: AppMode): string {
  return COLORS[mode];
}

function ContextBar({ percent }: { percent: number }): ReactNode {
  const width = 10;
  const filled = Math.round((percent / 100) * width);
  const empty = width - filled;
  const barColor = percent > 90 ? "red" : percent > 70 ? "yellow" : "green";

  return (
    <Text>
      <Text color={barColor}>{"█".repeat(filled)}</Text>
      <Text dimColor>{"░".repeat(empty)}</Text>
      <Text> {percent}%</Text>
    </Text>
  );
}

function formatCost(cost: number): string {
  return `$${cost.toFixed(2)}`;
}

export function StatusBarHeader(): ReactNode {
  const { state } = useApp();
  const usage = useDebouncedValue(state.usage, STATUSBAR_DEBOUNCE_MS);
  const session = useDebouncedValue(state.session, STATUSBAR_DEBOUNCE_MS);
  const mode = useDebouncedValue(getAppMode(state), STATUSBAR_DEBOUNCE_MS);
  const modeColor = getModeColor(mode);

  const modelName = usage.model || "no model";
  const cost = formatCost(usage.totalCost);
  const sessionInfo = session
    ? `${session.agentName} (${session.messageCount} msgs)`
    : "";

  return (
    <Box height={1} width="100%">
      <Box marginRight={1}>
        <Text color={modeColor} bold>── sage-tui</Text>
      </Box>
      <Box marginRight={1}>
        <Text> [{modelName}] </Text>
      </Box>
      <Box marginRight={1}>
        <Text>[</Text>
        <ContextBar percent={usage.contextUsagePercent} />
        <Text>]</Text>
      </Box>
      <Box marginRight={1}>
        <Text color="magenta">{cost}</Text>
      </Box>
      {sessionInfo && (
        <Box>
          <Text dimColor>{sessionInfo}</Text>
        </Box>
      )}
      <Box flexGrow={1}>
        <Text dimColor> {"─".repeat(20)}</Text>
      </Box>
    </Box>
  );
}

export function StatusBarFooter(): ReactNode {
  const { state } = useApp();
  const mode = useDebouncedValue(getAppMode(state), STATUSBAR_DEBOUNCE_MS);
  const runningToolName = useDebouncedValue(
    state.tools.find((tool) => tool.status === "running")?.name ?? "tool",
    STATUSBAR_DEBOUNCE_MS,
  );
  const debouncedCost = useDebouncedValue(
    state.usage.totalCost,
    STATUSBAR_DEBOUNCE_MS,
  );
  const debouncedError = useDebouncedValue(state.error, STATUSBAR_DEBOUNCE_MS);

  return (
    <Box height={1} width="100%">
      <FooterContent
        mode={mode}
        cost={debouncedCost}
        error={debouncedError}
        runningToolName={runningToolName}
      />
    </Box>
  );
}

function FooterContent({
  mode,
  cost,
  error,
  runningToolName,
}: {
  mode: AppMode;
  cost: number;
  error: string | null;
  runningToolName: string;
}): ReactNode {
  switch (mode) {
    case "idle":
      return (
        <Text dimColor>
          <Text color="cyan">Ctrl+B</Text> split | <Text color="cyan">Ctrl+E</Text> editor | <Text color="cyan">/</Text> commands | <Text color="cyan">Ctrl+C</Text> quit
        </Text>
      );

    case "streaming":
      return (
        <Text>
          <Text color="yellow">Streaming</Text> | {formatCost(cost)} | <Text color="cyan">ESC</Text> to cancel
        </Text>
      );

    case "tool": {
      return (
        <Text>
          <Text color="blue">Running: {runningToolName}</Text> | <Text color="cyan">ESC</Text> to cancel
        </Text>
      );
    }

    case "permission":
      return (
        <Text>
          <Text color="green">[y]</Text> Once{" "}
          <Text color="green">[a]</Text> Always{" "}
          <Text color="green">[s]</Text> Session{" "}
          <Text color="red">[n]</Text> Deny{" "}
          <Text color="yellow">[e]</Text> Edit
        </Text>
      );

    case "error":
      return (
        <Text color="red">
          Error: {error ?? "Unknown error"} | <Text color="cyan">ESC</Text> to dismiss
        </Text>
      );

    default:
      return <Text dimColor>Ready</Text>;
  }
}

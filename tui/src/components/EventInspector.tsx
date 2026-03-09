import { Box, Text } from "ink";
import { memo, type ReactNode } from "react";
import type { EventRecord } from "../types/events.js";

interface EventInspectorProps {
  event: EventRecord | null;
  maxHeight?: number;
}

function formatObject(value: Record<string, unknown> | undefined, maxLines: number): string {
  if (!value || Object.keys(value).length === 0) {
    return "n/a";
  }
  const text = JSON.stringify(value, null, 2);
  const lines = text.split("\n");
  if (lines.length > maxLines) {
    return lines.slice(0, maxLines).join("\n") + "\n...";
  }
  return text.length > 600 ? `${text.slice(0, 597)}...` : text;
}

function complexitySummary(payload: Record<string, unknown>): string | null {
  const complexity = typeof payload.complexity === "object" && payload.complexity !== null
    ? payload.complexity as Record<string, unknown>
    : null;
  if (!complexity) {
    return null;
  }
  const score = typeof complexity.score === "number" ? complexity.score : undefined;
  const level = typeof complexity.level === "string" ? complexity.level : undefined;
  const version = typeof complexity.version === "string" ? complexity.version : undefined;
  if (score === undefined || !level) {
    return null;
  }
  return `complexity=C${score} ${level}${version ? ` (${version})` : ""}`;
}

export const EventInspector = memo(function EventInspector({ event, maxHeight }: EventInspectorProps): ReactNode {
  // Border (2) + header (1) + metadata lines (~5-7) = ~9 rows of chrome;
  // remaining budget goes to the JSON payload.
  const payloadMaxLines = maxHeight ? Math.max(2, maxHeight - 9) : 20;

  return (
    <Box
      flexGrow={1}
      flexDirection="column"
      borderStyle="round"
      borderColor="gray"
      paddingX={1}
      {...(maxHeight ? { height: maxHeight, overflowY: "hidden" as const } : {})}
    >
      <Text bold>Inspector</Text>
      {!event ? (
        <Text dimColor>No event selected</Text>
      ) : (
        <>
          {complexitySummary(event.payload) && (
            <Text dimColor>{complexitySummary(event.payload)}</Text>
          )}
          <Text>{event.summary}</Text>
          <Text dimColor>{event.eventName}</Text>
          <Text dimColor>{`run=${event.runId ?? "n/a"}`}</Text>
          <Text dimColor>{`session=${event.sessionId ?? "n/a"}`}</Text>
          <Text dimColor>{`agent=${event.agentPath.join(" > ")} turn=${event.turnIndex ?? "n/a"}`}</Text>
          {typeof event.durationMs === "number" && (
            <Text dimColor>{`duration=${Math.round(event.durationMs)}ms`}</Text>
          )}
          {event.error && (
            <Text color="red">{`${event.error.type}: ${event.error.message}`}</Text>
          )}
          <Text dimColor>{formatObject(event.payload, payloadMaxLines)}</Text>
        </>
      )}
    </Box>
  );
});

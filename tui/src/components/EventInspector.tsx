import { Box, Text } from "ink";
import type { ReactNode } from "react";
import type { EventRecord } from "../types/events.js";

interface EventInspectorProps {
  event: EventRecord | null;
}

function formatObject(value: Record<string, unknown> | undefined): string {
  if (!value || Object.keys(value).length === 0) {
    return "n/a";
  }
  const text = JSON.stringify(value, null, 2);
  return text.length > 600 ? `${text.slice(0, 597)}...` : text;
}

export function EventInspector({ event }: EventInspectorProps): ReactNode {
  return (
    <Box flexDirection="column" borderStyle="round" borderColor="gray" paddingX={1}>
      <Text bold>Inspector</Text>
      {!event ? (
        <Text dimColor>No event selected</Text>
      ) : (
        <>
          <Text>{event.summary}</Text>
          <Text dimColor>{event.eventName}</Text>
          <Text dimColor>{`run=${event.runId ?? "n/a"} session=${event.sessionId ?? "n/a"}`}</Text>
          <Text dimColor>{`origin=${event.originatingSessionId ?? "n/a"} turn=${event.turnIndex ?? "n/a"}`}</Text>
          <Text dimColor>{`agent=${event.agentPath.join(" > ")}`}</Text>
          {typeof event.durationMs === "number" && (
            <Text dimColor>{`duration=${Math.round(event.durationMs)}ms`}</Text>
          )}
          {event.usage && (
            <Text dimColor>{`usage=${JSON.stringify(event.usage)}`}</Text>
          )}
          {event.error && (
            <Text color="red">{`${event.error.type}: ${event.error.message}`}</Text>
          )}
          <Text dimColor>{formatObject(event.payload)}</Text>
        </>
      )}
    </Box>
  );
}

import { Text } from "ink";
import { memo, type ReactNode } from "react";
import type { EventRecord } from "../types/events.js";
import { PaneFrame } from "./PaneFrame.js";

interface EventInspectorProps {
  event: EventRecord | null;
  width: number;
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

export const EventInspector = memo(function EventInspector({ event, width, maxHeight }: EventInspectorProps): ReactNode {
  // Top/bottom border (2) + metadata lines (~5-7) = ~8 rows of chrome;
  // remaining budget goes to the JSON payload.
  const payloadMaxLines = maxHeight ? Math.max(2, maxHeight - 8) : 20;

  return (
    <PaneFrame title="Inspector" width={width} height={maxHeight} flexGrow={1}>
      {!event ? (
        <Text dimColor>No event selected</Text>
      ) : (
        <>
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
    </PaneFrame>
  );
});

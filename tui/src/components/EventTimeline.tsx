import { Box, Text } from "ink";
import { memo, type ReactNode } from "react";
import type { EventRecord } from "../types/events.js";

interface EventTimelineProps {
  /** Pre-filtered events (already filtered by verbosity and user filters). */
  events: EventRecord[];
  selectedEventId: string | null;
  limit?: number;
  maxHeight?: number;
}

function statusColor(event: EventRecord): string {
  if (event.status === "error") return "red";
  if (event.status === "cancelled") return "yellow";
  if (event.status === "skipped") return "gray";
  if (event.phase === "start") return "blue";
  if (event.phase === "complete") return "green";
  return "cyan";
}

function durationText(event: EventRecord): string {
  if (typeof event.durationMs !== "number") {
    return "";
  }
  if (event.durationMs >= 1000) {
    return ` ${(event.durationMs / 1000).toFixed(1)}s`;
  }
  return ` ${Math.round(event.durationMs)}ms`;
}

function usageText(event: EventRecord): string {
  const totalTokens = event.usage?.totalTokens;
  if (typeof totalTokens === "number" && totalTokens > 0) {
    return ` ${totalTokens}tok`;
  }
  return "";
}

export const EventTimeline = memo(function EventTimeline({
  events,
  selectedEventId,
  limit,
  maxHeight,
}: EventTimelineProps): ReactNode {
  // Border (2) + header (1) = 3 rows of chrome; remaining rows are for events.
  const effectiveLimit = limit ?? (maxHeight ? Math.max(1, maxHeight - 3) : 18);
  const displayEvents = events.slice(-effectiveLimit);

  return (
    <Box
      width={80}
      flexShrink={0}
      flexDirection="column"
      borderStyle="round"
      borderColor="gray"
      paddingX={1}
      {...(maxHeight ? { height: maxHeight, overflowY: "hidden" as const } : {})}
    >
      <Text bold>Events</Text>
      {displayEvents.length === 0 ? (
        <Text dimColor>No events</Text>
      ) : (
        displayEvents.map((event) => {
          const selected = event.id === selectedEventId;
          return (
            <Box key={event.id}>
              <Text color={selected ? "magenta" : "gray"}>{selected ? ">" : " "}</Text>
              <Text color={statusColor(event)}>{event.category.padEnd(11, " ")}</Text>
              <Text>{event.summary}</Text>
              <Text dimColor>{durationText(event)}{usageText(event)}</Text>
            </Box>
          );
        })
      )}
    </Box>
  );
});

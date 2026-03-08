import { Box, Text } from "ink";
import type { ReactNode } from "react";
import {
  eventMatchesFilters,
  eventVisibleAtVerbosity,
  type EventFilters,
  type EventRecord,
  type VerbosityMode,
} from "../types/events.js";

interface EventTimelineProps {
  events: EventRecord[];
  selectedEventId: string | null;
  verbosity: VerbosityMode;
  filters: EventFilters;
  limit?: number;
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

export function EventTimeline({
  events,
  selectedEventId,
  verbosity,
  filters,
  limit = 18,
}: EventTimelineProps): ReactNode {
  const visibleEvents = events
    .filter((event) => eventVisibleAtVerbosity(event, verbosity))
    .filter((event) => eventMatchesFilters(event, filters))
    .slice(-limit);

  return (
    <Box flexDirection="column" borderStyle="round" borderColor="gray" paddingX={1}>
      <Text bold>Events</Text>
      {visibleEvents.length === 0 ? (
        <Text dimColor>No events</Text>
      ) : (
        visibleEvents.map((event) => {
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
}

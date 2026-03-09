import { useMemo } from "react";
import type { BlockState } from "../state/blockReducer.js";
import { eventMatchesFilters, eventVisibleAtVerbosity, type EventRecord, type RunSummary } from "../types/events.js";

export function useEventPaneState(state: BlockState): {
  visibleEvents: EventRecord[];
  selectedEvent: EventRecord | null;
  activeRun: RunSummary | undefined;
} {
  const visibleEvents = useMemo(
    () =>
      state.events
        .filter((event) => eventVisibleAtVerbosity(event, state.ui.verbosity))
        .filter((event) => eventMatchesFilters(event, state.ui.filters)),
    [state.events, state.ui.filters, state.ui.verbosity],
  );

  const selectedEvent = useMemo(
    () =>
      visibleEvents.find((event) => event.id === state.ui.selectedEventId)
      ?? state.events.find((event) => event.id === state.ui.selectedEventId)
      ?? visibleEvents.at(-1)
      ?? null,
    [visibleEvents, state.events, state.ui.selectedEventId],
  );

  const activeRun = state.activeStream?.runId
    ? state.runs[state.activeStream.runId]
    : Object.values(state.runs).at(-1);

  return { visibleEvents, selectedEvent, activeRun };
}

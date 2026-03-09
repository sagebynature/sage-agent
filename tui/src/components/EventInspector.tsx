import { Box, Text, useInput } from "ink";
import { memo, type ReactNode, useEffect, useMemo, useState } from "react";
import type { EventRecord } from "../types/events.js";
import { PaneFrame } from "./PaneFrame.js";

interface EventInspectorProps {
  event: EventRecord | null;
  width: number;
  maxHeight?: number;
}

type InspectorLine = {
  text: string;
  color?: string;
};

function formatObject(value: Record<string, unknown> | undefined): InspectorLine[] {
  if (!value || Object.keys(value).length === 0) {
    return [{ text: "payload: n/a", color: "gray" }];
  }

  return [
    { text: "payload:", color: "gray" },
    ...JSON.stringify(value, null, 2).split("\n").map((line) => ({ text: line, color: "gray" })),
  ];
}

function clipLine(line: string, width: number): string {
  if (width <= 0) {
    return "";
  }
  if (line.length <= width) {
    return line.padEnd(width, " ");
  }
  if (width === 1) {
    return "…";
  }
  return `${line.slice(0, width - 1)}…`;
}

export function buildInspectorLines(event: EventRecord | null): InspectorLine[] {
  if (!event) {
    return [{ text: "No event selected", color: "gray" }];
  }

  const lines: InspectorLine[] = [
    { text: event.summary },
    { text: event.eventName, color: "gray" },
    { text: `run=${event.runId ?? "n/a"}`, color: "gray" },
    { text: `session=${event.sessionId ?? "n/a"}`, color: "gray" },
    { text: `agent=${event.agentPath.join(" > ")} turn=${event.turnIndex ?? "n/a"}`, color: "gray" },
  ];

  if (typeof event.durationMs === "number") {
    lines.push({ text: `duration=${Math.round(event.durationMs)}ms`, color: "gray" });
  }

  if (event.error) {
    lines.push({ text: `${event.error.type}: ${event.error.message}`, color: "red" });
  }

  lines.push(...formatObject(event.payload));
  return lines;
}

export function visibleInspectorLines(lines: InspectorLine[], scrollOffset: number, windowSize: number): InspectorLine[] {
  if (windowSize <= 0) {
    return [];
  }

  const maxOffset = Math.max(0, lines.length - windowSize);
  const safeOffset = Math.min(Math.max(0, scrollOffset), maxOffset);
  return lines.slice(safeOffset, safeOffset + windowSize);
}

export function resolveScrollbarRange(totalLines: number, windowSize: number, scrollOffset: number): {
  thumbStart: number;
  thumbSize: number;
} {
  if (windowSize <= 0 || totalLines <= windowSize) {
    return { thumbStart: 0, thumbSize: 0 };
  }

  const maxOffset = Math.max(1, totalLines - windowSize);
  const trackSize = windowSize;
  const thumbSize = Math.max(1, Math.round((windowSize / totalLines) * trackSize));
  const maxThumbStart = Math.max(0, trackSize - thumbSize);
  const thumbStart = Math.min(
    maxThumbStart,
    Math.round((Math.max(0, scrollOffset) / maxOffset) * maxThumbStart),
  );

  return { thumbStart, thumbSize };
}

export const EventInspector = memo(function EventInspector({ event, width, maxHeight }: EventInspectorProps): ReactNode {
  const [scrollOffset, setScrollOffset] = useState(0);
  const inspectorLines = useMemo(() => buildInspectorLines(event), [event]);
  const bodyHeight = maxHeight ? Math.max(1, maxHeight - 2) : 20;
  const maxOffset = Math.max(0, inspectorLines.length - bodyHeight);
  const contentWidth = Math.max(1, width - 6);
  const visibleLines = useMemo(
    () => visibleInspectorLines(inspectorLines, scrollOffset, bodyHeight),
    [bodyHeight, inspectorLines, scrollOffset],
  );
  const { thumbStart, thumbSize } = useMemo(
    () => resolveScrollbarRange(inspectorLines.length, bodyHeight, scrollOffset),
    [bodyHeight, inspectorLines.length, scrollOffset],
  );

  useEffect(() => {
    setScrollOffset(0);
  }, [event?.id]);

  useEffect(() => {
    if (scrollOffset > maxOffset) {
      setScrollOffset(maxOffset);
    }
  }, [maxOffset, scrollOffset]);

  useInput((_input, key) => {
    if (key.pageDown) {
      setScrollOffset((current) => Math.min(maxOffset, current + Math.max(1, bodyHeight - 1)));
      return;
    }

    if (key.pageUp) {
      setScrollOffset((current) => Math.max(0, current - Math.max(1, bodyHeight - 1)));
    }
  });

  return (
    <PaneFrame title="Inspector" width={width} height={maxHeight} flexGrow={1}>
      {visibleLines.map((line, index) => {
        const absoluteIndex = index + Math.min(scrollOffset, maxOffset);
        const isThumb = thumbSize > 0 && absoluteIndex >= thumbStart && absoluteIndex < thumbStart + thumbSize;

        return (
          <Box key={`${event?.id ?? "empty"}-${absoluteIndex}`}>
            <Text color={line.color}>{clipLine(line.text, contentWidth)}</Text>
            <Text dimColor={!isThumb}>{isThumb ? "█" : "│"}</Text>
          </Box>
        );
      })}
    </PaneFrame>
  );
});

import { Box, Text } from "ink";
import { memo, type ReactNode } from "react";
import type { ActiveStream } from "../types/blocks.js";
import { ActiveStreamView } from "./ActiveStreamView.js";

interface ActiveTaskDockProps {
  streams: ActiveStream[];
  width?: number;
}

export const ActiveTaskDock = memo(function ActiveTaskDock({
  streams,
  width,
}: ActiveTaskDockProps): ReactNode {
  const activeOnlyStreams = streams
    .map((stream) => ({
      ...stream,
      tools: stream.tools.filter((tool) => tool.status === "running"),
    }))
    .filter((stream) => stream.tools.length > 0 || stream.isThinking || stream.content.length > 0);

  if (activeOnlyStreams.length === 0) {
    return null;
  }

  const orderedStreams = [...activeOnlyStreams].reverse();

  return (
    <Box flexDirection="column" width={width} paddingX={1}>
      <Text dimColor>{"Active Tasks"}</Text>
      {orderedStreams.map((stream) => (
        <Box key={stream.runId} flexDirection="column" marginTop={1}>
          <ActiveStreamView stream={stream} />
        </Box>
      ))}
    </Box>
  );
});

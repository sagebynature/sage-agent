import { Box, Text } from "ink";
import type { ReactNode } from "react";
import type { ActiveStream } from "../types/blocks.js";
import { renderMarkdown } from "../renderer/MarkdownRenderer.js";

interface ActiveStreamViewProps {
  stream: ActiveStream | null;
}

function formatElapsed(startedAt: number): string {
  const elapsed = Math.floor((Date.now() - startedAt) / 1000);
  if (elapsed < 60) return `${elapsed}s`;
  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  return `${min}m ${sec}s`;
}

export function ActiveStreamView({ stream }: ActiveStreamViewProps): ReactNode {
  if (!stream) return null;

  const runningTools = stream.tools.filter((t) => t.status === "running");

  return (
    <Box flexDirection="column">
      {runningTools.map((tool) => (
        <Text key={tool.callId}>
          {"● "}{tool.name}
          {tool.arguments.path ? ` ${tool.arguments.path}` : ""}
          {tool.arguments.command ? ` ${tool.arguments.command}` : ""}
          <Text dimColor>{"  ... running"}</Text>
        </Text>
      ))}
      {stream.isThinking ? (
        <Box>
          <Text color="cyan">{"✻ Thinking..."}</Text>
          <Text dimColor>{" ("}{formatElapsed(stream.startedAt)}{")"}</Text>
        </Box>
      ) : stream.content.length > 0 ? (
        <Box flexDirection="column">
          <Text>{"● "}{renderMarkdown(stream.content, true)}</Text>
        </Box>
      ) : null}
    </Box>
  );
}

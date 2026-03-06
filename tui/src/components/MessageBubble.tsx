import { Box, Text } from "ink";
import React, { type ReactNode } from "react";
import type { ChatMessage } from "../types/state.js";

interface MessageBubbleProps {
  message: ChatMessage;
}

// Format timestamp as relative time
function formatRelativeTime(timestamp: number): string {
  const now = Date.now();
  const diffMs = now - timestamp;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);

  if (diffSec < 10) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffMin < 60) return `${diffMin}m ago`;
  return `${diffHr}h ago`;
}

export const MessageBubble = React.memo(function MessageBubble({ message }: MessageBubbleProps): ReactNode {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const isSystem = message.role === "system";

  // Role label
  const roleLabel = isUser ? "You" :
    isAssistant ? "Sage" :
    isSystem ? "System" : "Tool";

  // Role color
  const roleColor = isUser ? "cyan" :
    isAssistant ? "magenta" :
    isSystem ? "gray" : "blue";

  // Content to display
  const content = message.content ?? "";

  // Truncate very long messages (>2000 chars) with "show more" note
  const maxChars = 2000;
  const isTruncated = content.length > maxChars;
  const displayContent = isTruncated ? content.slice(0, maxChars) : content;

  if (isSystem) {
    return (
      <Box justifyContent="center" paddingY={0}>
        <Text dimColor italic>{displayContent}</Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column" paddingY={0} marginBottom={1}>
      <Box>
        <Text color={roleColor} bold>[{roleLabel}]</Text>
        <Text dimColor> {formatRelativeTime(message.timestamp)}</Text>
      </Box>
      <Box paddingLeft={0}>
        <Text>
          {displayContent}
          {message.isStreaming && <Text color="yellow"> ⠙</Text>}
        </Text>
      </Box>
      {isTruncated && (
        <Text dimColor italic>... (truncated, {content.length} chars total)</Text>
      )}
    </Box>
  );
}, (previous, next) => {
  return (
    previous.message.id === next.message.id &&
    previous.message.content === next.message.content &&
    previous.message.isStreaming === next.message.isStreaming
  );
});

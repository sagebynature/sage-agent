import { Box, Text } from "ink";
import Spinner from "ink-spinner";
import { type ReactNode, useMemo } from "react";
import { useApp } from "../state/AppContext.js";
import { MessageBubble } from "./MessageBubble.js";

interface ChatViewProps {
  height?: number;
}

const VISIBLE_WINDOW = 50;

function WelcomeScreen(): ReactNode {
  return (
    <Box flexDirection="column" alignItems="center" justifyContent="center" flexGrow={1} paddingY={2}>
      <Text bold color="magenta">WELCOME TO SAGE-TUI</Text>
      <Text>Your AI pair programmer companion.</Text>
      <Text> </Text>
      <Text>Get started by:</Text>
      <Text color="cyan">  • Asking a question about your codebase</Text>
      <Text color="cyan">  • Running a shell command with "!"</Text>
      <Text color="cyan">  • Using "/" to see all available commands</Text>
      <Text> </Text>
      <Text dimColor>(Type /help to learn more about capabilities)</Text>
    </Box>
  );
}

function StreamingWaitIndicator(): ReactNode {
  return (
    <Box paddingY={0} marginBottom={1}>
      <Box>
        <Text color="magenta" bold>[Sage]</Text>
      </Box>
      <Box marginLeft={1}>
        <Spinner type="dots" />
        <Text dimColor> Thinking...</Text>
      </Box>
    </Box>
  );
}

export function ChatView({ height }: ChatViewProps): ReactNode {
  const { state } = useApp();
  const { messages, isStreaming } = state;

  const visibleMessages = useMemo(() => {
    if (messages.length <= VISIBLE_WINDOW) {
      return messages;
    }

    return messages.slice(-VISIBLE_WINDOW);
  }, [messages]);

  const hiddenCount = messages.length - visibleMessages.length;

  const messageElements = useMemo(() => {
    return visibleMessages.map((msg) => (
      <MessageBubble key={msg.id} message={msg} />
    ));
  }, [visibleMessages]);

  if (messages.length === 0 && !isStreaming) {
    return <WelcomeScreen />;
  }

  const lastMessage = messages[messages.length - 1];
  const isLastAssistantStreaming = lastMessage?.role === "assistant" && lastMessage.isStreaming;

  // Show waiting indicator if streaming but no assistant message yet
  // or if the last message is not the assistant responding
  const showWaitIndicator = isStreaming && !isLastAssistantStreaming && (
    !lastMessage || lastMessage.role !== "assistant"
  );

  return (
    <Box flexDirection="column" flexGrow={1} overflow="hidden" height={height}>
      <Box flexDirection="column" flexGrow={1} paddingX={1}>
        {hiddenCount > 0 && <Text dimColor>({hiddenCount} earlier messages)</Text>}
        {messageElements}

        {showWaitIndicator && <StreamingWaitIndicator />}
      </Box>
    </Box>
  );
}

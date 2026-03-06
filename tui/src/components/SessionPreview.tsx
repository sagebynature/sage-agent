import { Box, Text } from 'ink';
import type { SessionInfo } from '../types/protocol.js';

interface SessionPreviewProps {
  session: SessionInfo | null;
}

export function SessionPreview({ session }: SessionPreviewProps) {
  if (!session) {
    return (
      <Box borderStyle="round" borderColor="gray" padding={1} flexDirection="column" width="50%" height="100%">
        <Box height="100%" justifyContent="center" alignItems="center">
          <Text color="gray">Select a session to preview</Text>
        </Box>
      </Box>
    );
  }

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return dateString;
    }
  };

  return (
    <Box borderStyle="round" borderColor="blue" padding={1} flexDirection="column" width="50%" height="100%">
      <Box marginBottom={1} borderStyle="single" borderColor="blue" paddingX={1} alignSelf="center">
        <Text bold color="blue">Session Details</Text>
      </Box>

      <Box flexDirection="column" gap={1}>
        <Box>
          <Text bold color="cyan">ID: </Text>
          <Text>{session.id}</Text>
        </Box>

        <Box>
          <Text bold color="cyan">Agent: </Text>
          <Text>{session.agentName}</Text>
        </Box>

        <Box>
          <Text bold color="cyan">Model: </Text>
          <Text>{session.model || 'Unknown'}</Text>
        </Box>

        <Box>
          <Text bold color="cyan">Created: </Text>
          <Text>{formatDate(session.createdAt)}</Text>
        </Box>

        <Box>
          <Text bold color="cyan">Updated: </Text>
          <Text>{formatDate(session.updatedAt)}</Text>
        </Box>

        <Box>
          <Text bold color="cyan">Messages: </Text>
          <Text>{session.messageCount}</Text>
        </Box>

        <Box>
          <Text bold color="cyan">Cost: </Text>
          <Text>${session.totalCost?.toFixed(4) || '0.0000'}</Text>
        </Box>

        <Box marginTop={1} flexDirection="column">
          <Text bold color="cyan">First Message:</Text>
          <Box borderStyle="single" borderColor="gray" padding={1} height={10}>
            <Text wrap="wrap">
              {session.firstMessage || '(No content)'}
            </Text>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}

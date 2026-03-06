import React, { useState } from 'react';
import { Box, Text, useInput } from 'ink';
import { RetryCountdown } from './RetryCountdown.js';
import { TokenUsageBar } from './TokenUsageBar.js';

export type ErrorType =
  | 'rate_limit'
  | 'context_full'
  | 'auth_error'
  | 'network_error'
  | 'backend_crash'
  | 'tool_error'
  | 'token_exhaustion'
  | 'unknown';

export interface ErrorInfo {
  type: ErrorType;
  message: string;
  data?: Record<string, unknown>;
}

export interface ErrorStatesProps {
  error: ErrorInfo;
  onRetry?: () => void;
  onDismiss?: () => void;
  onRestart?: () => void;
}

export const ErrorStates: React.FC<ErrorStatesProps> = ({
  error,
  onRetry,
  onDismiss,
  onRestart
}) => {
  const [showStack, setShowStack] = useState(false);
  const [networkRetries, setNetworkRetries] = useState(0);

  useInput((input, key) => {
    if (error.type === 'tool_error' && input === 's') {
      setShowStack((prev) => !prev);
    }
    if (error.type === 'network_error' && input === 'r' && onRetry) {
      setNetworkRetries((prev) => prev + 1);
      onRetry();
    }
    if (key.escape && onDismiss) {
      onDismiss();
    }
  });

  const renderContent = () => {
    switch (error.type) {
      case 'rate_limit': {
        const retryAfter = (error.data?.['retryAfter'] as number) || 30;
        return (
          <Box flexDirection="column" gap={1}>
            <Text color="yellow">⏱ Rate limited</Text>
            <RetryCountdown
              seconds={retryAfter}
              onComplete={() => onRetry?.()}
            />
            <Text dimColor>Auto-retrying...</Text>
          </Box>
        );
      }

      case 'context_full': {
        const usage = (error.data?.['usage'] as { prompt: number, completion: number, max: number }) || { prompt: 0, completion: 0, max: 1 };
        return (
          <Box flexDirection="column" gap={1}>
            <Text color="yellow">⚠ Context {Math.round(((usage.prompt + usage.completion) / usage.max) * 100)}% full</Text>
            <TokenUsageBar {...usage} />
            <Text>Suggestion: Use <Text color="cyan">/compact</Text> to reduce context size.</Text>
          </Box>
        );
      }

      case 'auth_error': {
        const provider = (error.data?.['provider'] as string) || 'Unknown Provider';
        return (
          <Box flexDirection="column" gap={1}>
            <Text color="red">Auth Error: {provider}</Text>
            <Text>Please check your configuration or API key.</Text>
            <Text dimColor>(Key is hidden for security)</Text>
          </Box>
        );
      }

      case 'network_error': {
        const lastConnected = (error.data?.['lastConnected'] as string) || 'unknown';
        return (
          <Box flexDirection="column" gap={1}>
            <Text color="red">Network Error</Text>
            <Text>Last connected: {lastConnected}</Text>
            {onRetry && (
              <Box>
                <Text color="cyan" inverse> Press R to Retry </Text>
                <Text> (Backoff: {Math.min(30, Math.pow(2, networkRetries))}s)</Text>
              </Box>
            )}
          </Box>
        );
      }

      case 'backend_crash': {
        const exitCode = (error.data?.['exitCode'] as number) || 1;
        const restarts = (error.data?.['restarts'] as number) || 0;

        return (
          <Box flexDirection="column" gap={1}>
            <Text color="red" bold>Backend Crashed (Code: {exitCode})</Text>
            {restarts < 3 ? (
               onRestart ? <Text color="green">Auto-restarting ({restarts + 1}/3)...</Text> : <Text>Restarting unavailable</Text>
            ) : (
              <Box flexDirection="column">
                <Text color="red">Max restarts exceeded.</Text>
                <Text>Please check logs at: <Text underline>sage-agent.log</Text></Text>
              </Box>
            )}
          </Box>
        );
      }

      case 'tool_error': {
        const toolName = (error.data?.['toolName'] as string) || 'unknown_tool';
        const stack = (error.data?.['stack'] as string) || '';

        return (
          <Box flexDirection="column" gap={1}>
            <Text color="red">Tool Execution Error: {toolName}</Text>
            <Text>{error.message}</Text>
            {stack && (
              <Box flexDirection="column">
                 <Text dimColor>Stack trace (Press S to toggle):</Text>
                 {showStack && <Text dimColor>{stack}</Text>}
              </Box>
            )}
          </Box>
        );
      }

      case 'token_exhaustion': {
        return (
          <Box flexDirection="column" gap={1}>
            <Text color="red">Token Limit Exhausted</Text>
            <Text>Cost estimate exceeded or hard limit reached.</Text>
            <Text>Suggestion: Switch to a cheaper model or increase limit.</Text>
          </Box>
        );
      }

      case 'unknown':
      default: {
        return (
          <Box flexDirection="column" gap={1}>
            <Text color="red">Error: {error.message}</Text>
            <Text>Suggestion: Try <Text color="cyan">/reset</Text></Text>
            <Text dimColor>Hint: Copy error message for support.</Text>
          </Box>
        );
      }
    }
  };

  const borderColor =
    ['auth_error', 'backend_crash', 'tool_error', 'token_exhaustion', 'network_error'].includes(error.type) ? 'red' :
    ['rate_limit', 'context_full'].includes(error.type) ? 'yellow' :
    'white';

  return (
    <Box borderStyle="round" borderColor={borderColor} padding={1}>
      {renderContent()}
    </Box>
  );
};

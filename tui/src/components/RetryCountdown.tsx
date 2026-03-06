import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';

export interface RetryCountdownProps {
  seconds: number;
  onComplete: () => void;
}

export const RetryCountdown: React.FC<RetryCountdownProps> = ({ seconds, onComplete }) => {
  const [timeLeft, setTimeLeft] = useState(seconds);

  useEffect(() => {
    if (timeLeft === 0) {
      onComplete();
      return;
    }

    const timer = setInterval(() => {
      setTimeLeft((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(timer);
  }, [timeLeft, onComplete]);

  const totalWidth = 40;
  const progress = Math.max(0, Math.min(1, (seconds - timeLeft) / seconds));
  const filledWidth = Math.floor(progress * totalWidth);
  const emptyWidth = totalWidth - filledWidth;

  const progressBar = '█'.repeat(filledWidth) + '░'.repeat(emptyWidth);

  return (
    <Box flexDirection="column" gap={1}>
      <Text>Retrying in {timeLeft}s...</Text>
      <Text color="cyan">
        {progressBar}
      </Text>
    </Box>
  );
};

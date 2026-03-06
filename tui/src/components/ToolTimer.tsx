import { Text } from 'ink';
import { useState, useEffect } from 'react';

interface ToolTimerProps {
  startTime?: number;
  endTime?: number;
}

const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${Math.floor(ms)}ms`;
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
};

export const ToolTimer = ({ startTime, endTime }: ToolTimerProps) => {
  const [elapsed, setElapsed] = useState<number>(0);

  useEffect(() => {
    if (!startTime || endTime) return;

    const interval = setInterval(() => {
      setElapsed(Date.now() - startTime);
    }, 100);

    return () => clearInterval(interval);
  }, [startTime, endTime]);

  if (!startTime) return null;

  const duration = endTime ? endTime - startTime : Math.max(0, Date.now() - startTime);

  // If we have an endTime, we use the calculated duration.
  // If running, we use the state 'elapsed' (which tracks Date.now() - startTime),
  // but initial render might differ slightly, so we sync it.
  const displayDuration = endTime ? duration : (elapsed || Date.now() - startTime);

  return <Text color="dim">{formatDuration(displayDuration)}</Text>;
};

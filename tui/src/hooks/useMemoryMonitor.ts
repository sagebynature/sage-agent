import { useEffect, useState } from "react";

export const MEMORY_WARNING_EVENT = "sage:memory-warning";

export interface MemoryWarningAction {
  type: "MEMORY_WARNING";
  heapUsedMB: number;
  limitMB: number;
}

export interface MemoryMonitorState {
  heapUsedMB: number;
  isWarning: boolean;
}

function getHeapUsedMB(): number {
  return process.memoryUsage().heapUsed / (1024 * 1024);
}

export function useMemoryMonitor(
  limitMB = 200,
  intervalMs = 10_000,
): MemoryMonitorState {
  const [heapUsedMB, setHeapUsedMB] = useState(() => getHeapUsedMB());
  const [isWarning, setIsWarning] = useState(false);

  useEffect(() => {
    const threshold = limitMB * 0.8;

    const check = () => {
      const used = getHeapUsedMB();
      setHeapUsedMB(used);

      const warning = used > threshold;
      setIsWarning(warning);

      if (warning) {
        const action: MemoryWarningAction = {
          type: "MEMORY_WARNING",
          heapUsedMB: used,
          limitMB,
        };
        process.emit(MEMORY_WARNING_EVENT, action);
      }
    };

    check();
    const interval = setInterval(check, intervalMs);
    return () => {
      clearInterval(interval);
    };
  }, [intervalMs, limitMB]);

  return {
    heapUsedMB,
    isWarning,
  };
}

import { useInput } from "ink";
import { useRef } from "react";

const DOUBLE_PRESS_WINDOW_MS = 1000;

export function useExitHandler(
  isStreaming: boolean,
  onCancel: () => void,
  onExit: () => void,
): void {
  const lastCtrlCTimestampRef = useRef(0);

  useInput((input, key) => {
    const isCtrlC = (key.ctrl && input === "c") || input === "\u0003";
    if (!isCtrlC) {
      return;
    }

    const now = Date.now();

    if (!isStreaming) {
      onExit();
      lastCtrlCTimestampRef.current = now;
      return;
    }

    const elapsed = now - lastCtrlCTimestampRef.current;
    if (elapsed <= DOUBLE_PRESS_WINDOW_MS) {
      onExit();
      lastCtrlCTimestampRef.current = now;
      return;
    }

    lastCtrlCTimestampRef.current = now;
    onCancel();
  });
}

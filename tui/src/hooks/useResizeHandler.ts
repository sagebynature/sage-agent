import { useStdout } from "ink";
import { useEffect, useState } from "react";

const RESIZE_SETTLE_MS = 100;

interface ResizeSource {
  columns?: number;
  rows?: number;
  on(event: "resize", listener: () => void): void;
  off(event: "resize", listener: () => void): void;
}

export interface ResizeState {
  width: number;
  height: number;
  isResizing: boolean;
}

function readDimensions(source: ResizeSource | null | undefined): {
  width: number;
  height: number;
} {
  return {
    width: source?.columns ?? 80,
    height: source?.rows ?? 24,
  };
}

export function useResizeHandler(): ResizeState {
  const inkStdout = useStdout().stdout;
  const resizeSource: ResizeSource | null =
    (inkStdout as unknown as ResizeSource | undefined) ??
    (process.stdout as unknown as ResizeSource | undefined) ??
    null;
  const [state, setState] = useState<ResizeState>(() => {
    const { width, height } = readDimensions(resizeSource);
    return {
      width,
      height,
      isResizing: false,
    };
  });

  useEffect(() => {
    if (!resizeSource) {
      return;
    }

    let settleTimer: ReturnType<typeof setTimeout> | null = null;

    const onResize = () => {
      setState((prev) => ({ ...prev, isResizing: true }));

      if (settleTimer) {
        clearTimeout(settleTimer);
      }

      settleTimer = setTimeout(() => {
        const { width, height } = readDimensions(resizeSource);
        setState({
          width,
          height,
          isResizing: false,
        });
        settleTimer = null;
      }, RESIZE_SETTLE_MS);
    };

    resizeSource.on("resize", onResize);

    return () => {
      resizeSource.off("resize", onResize);
      if (settleTimer) {
        clearTimeout(settleTimer);
      }
    };
  }, [resizeSource]);

  return state;
}

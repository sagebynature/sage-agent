import { useState, useCallback, useRef } from "react";

interface InputHistory {
  entries: string[];
  addEntry: (text: string) => void;
  navigateUp: () => string | undefined;
  navigateDown: () => string | undefined;
  search: (query: string) => string[];
  reset: () => void;
  currentIndex: number;
}

export function useInputHistory(maxEntries = 100): InputHistory {
  const [entries, setEntries] = useState<string[]>([]);
  const indexRef = useRef(-1);

  const addEntry = useCallback((text: string) => {
    if (!text.trim()) return;
    setEntries(prev => {
      const next = [text, ...prev.filter(e => e !== text)];
      return next.slice(0, maxEntries);
    });
    indexRef.current = -1;
  }, [maxEntries]);

  const navigateUp = useCallback((): string | undefined => {
    if (entries.length === 0) return undefined;

    const nextIndex = Math.min(indexRef.current + 1, entries.length - 1);
    indexRef.current = nextIndex;

    return entries[nextIndex];
  }, [entries]);

  const navigateDown = useCallback((): string | undefined => {
    if (indexRef.current === -1) return undefined;

    const nextIndex = indexRef.current - 1;
    indexRef.current = nextIndex;

    if (nextIndex === -1) {
      return undefined;
    }

    return entries[nextIndex];
  }, [entries]);

  const search = useCallback((query: string): string[] => {
    return entries.filter(e => e.toLowerCase().includes(query.toLowerCase()));
  }, [entries]);

  const reset = useCallback(() => {
    indexRef.current = -1;
  }, []);

  return { entries, addEntry, navigateUp, navigateDown, search, reset, currentIndex: indexRef.current };
}

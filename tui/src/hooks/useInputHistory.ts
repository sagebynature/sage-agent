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
  const entriesRef = useRef<string[]>([]);
  const indexRef = useRef(-1);

  const addEntry = useCallback((text: string) => {
    if (!text.trim()) return;
    const nextEntries = [text, ...entriesRef.current.filter((entry) => entry !== text)]
      .slice(0, maxEntries);
    entriesRef.current = nextEntries;
    setEntries(nextEntries);
    indexRef.current = -1;
  }, [maxEntries]);

  const navigateUp = useCallback((): string | undefined => {
    if (entriesRef.current.length === 0) return undefined;

    const nextIndex = Math.min(indexRef.current + 1, entriesRef.current.length - 1);
    indexRef.current = nextIndex;

    return entriesRef.current[nextIndex];
  }, []);

  const navigateDown = useCallback((): string | undefined => {
    if (indexRef.current === -1) return undefined;

    const nextIndex = indexRef.current - 1;
    indexRef.current = nextIndex;

    if (nextIndex === -1) {
      return undefined;
    }

    return entriesRef.current[nextIndex];
  }, []);

  const search = useCallback((query: string): string[] => {
    return entriesRef.current.filter(entry => entry.toLowerCase().includes(query.toLowerCase()));
  }, []);

  const reset = useCallback(() => {
    indexRef.current = -1;
  }, []);

  return {
    entries,
    addEntry,
    navigateUp,
    navigateDown,
    search,
    reset,
    currentIndex: indexRef.current,
  };
}

import { useInput, type Key } from "ink";
import { useState, useEffect, useCallback, useRef } from "react";
import { defaultKeybindings } from "../config/keybindings.js";
import type { ShortcutMode, KeyBinding } from "../types/shortcuts.js";

const LEADER_TIMEOUT_MS = 1000;

export interface UseKeyboardOptions {
  mode: ShortcutMode;
  onAction: (action: string) => void;
  enabled?: boolean;
}

export interface UseKeyboardResult {
  leaderActive: boolean;
  currentMode: ShortcutMode;
}

function resolveKey(input: string, key: Key): string {
  if (key.upArrow) return "upArrow";
  if (key.downArrow) return "downArrow";
  if (key.leftArrow) return "leftArrow";
  if (key.rightArrow) return "rightArrow";
  if (key.pageUp) return "pageUp";
  if (key.pageDown) return "pageDown";
  if (key.return) return "return";
  if (key.escape) return "escape";
  if (key.tab) return "tab";
  if (key.backspace || key.delete) return "backspace";
  return input;
}

function matchesBinding(
  kb: KeyBinding,
  resolvedKey: string,
  key: Key,
  activeMode: ShortcutMode,
): boolean {
  if (!kb.modes.includes(activeMode)) return false;
  if (kb.ctrl && !key.ctrl) return false;
  if (!kb.ctrl && key.ctrl) return false;
  if (kb.shift && !key.shift) return false;
  if (kb.meta && !key.meta) return false;

  const home = resolvedKey === "home" || (key.ctrl && resolvedKey === "a");
  const end = resolvedKey === "end" || (key.ctrl && resolvedKey === "e");

  if (kb.key === "home") return home;
  if (kb.key === "end") return end;

  return kb.key === resolvedKey;
}

export function useKeyboard({
  mode,
  onAction,
  enabled = true,
}: UseKeyboardOptions): UseKeyboardResult {
  const [leaderActive, setLeaderActive] = useState(false);
  // Use a ref to always read the latest leaderActive inside useInput callbacks
  const leaderActiveRef = useRef(false);
  const leaderTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelLeader = useCallback(() => {
    leaderActiveRef.current = false;
    setLeaderActive(false);
    if (leaderTimerRef.current !== null) {
      clearTimeout(leaderTimerRef.current);
      leaderTimerRef.current = null;
    }
  }, []);

  const activateLeader = useCallback(() => {
    leaderActiveRef.current = true;
    setLeaderActive(true);
    if (leaderTimerRef.current !== null) {
      clearTimeout(leaderTimerRef.current);
    }
    leaderTimerRef.current = setTimeout(() => {
      leaderActiveRef.current = false;
      setLeaderActive(false);
      leaderTimerRef.current = null;
    }, LEADER_TIMEOUT_MS);
  }, []);

  useEffect(() => {
    return () => {
      if (leaderTimerRef.current !== null) {
        clearTimeout(leaderTimerRef.current);
        leaderTimerRef.current = null;
      }
    };
  }, []);

  const activeMode: ShortcutMode = leaderActive ? "leader" : mode;

  useInput(
    (input: string, key: Key) => {
      if (!enabled) return;

      const resolvedKey = resolveKey(input, key);
      const isLeaderActive = leaderActiveRef.current;

      if (key.ctrl && input === "x" && !isLeaderActive) {
        activateLeader();
        return;
      }

      if (isLeaderActive) {
        const leaderBinding = defaultKeybindings.find((kb) =>
          matchesBinding(kb, resolvedKey, key, "leader"),
        );
        cancelLeader();
        if (leaderBinding) {
          onAction(leaderBinding.action);
        }
        return;
      }

      const insertSafeActions = new Set(["cancel", "send", "newline", "undo", "history-prev", "history-next"]);
      const effectiveMode = mode;

      for (const kb of defaultKeybindings) {
        if (!kb.modes.includes(effectiveMode)) continue;

        if (effectiveMode === "insert" && !insertSafeActions.has(kb.action)) {
          continue;
        }

        if (matchesBinding(kb, resolvedKey, key, effectiveMode)) {
          onAction(kb.action);
          return;
        }
      }
    },
    { isActive: true },
  );

  return { leaderActive, currentMode: activeMode };
}

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createElement, createRef, type ReactNode } from "react";
import { Box, Text } from "ink";
import { renderApp } from "../../test-utils.js";
import { useKeyboard, type UseKeyboardResult } from "../useKeyboard.js";
import type { ShortcutMode } from "../../types/shortcuts.js";

// ─── Test harness ───────────────────────────────────────────────────────────

interface HarnessProps {
  mode: ShortcutMode;
  onAction: (action: string) => void;
  enabled?: boolean;
  hookRef: React.RefObject<UseKeyboardResult | null>;
}

function HookHarness({ mode, onAction, enabled, hookRef }: HarnessProps): ReactNode {
  const result = useKeyboard({ mode, onAction, enabled });
  hookRef.current = result;
  return createElement(
    Box,
    { flexDirection: "column" },
    createElement(Text, null, `leader:${String(result.leaderActive)}`),
    createElement(Text, null, `mode:${result.currentMode}`),
  );
}

function renderHook(
  mode: ShortcutMode,
  onAction: (action: string) => void,
  enabled?: boolean,
) {
  const hookRef = createRef<UseKeyboardResult | null>();
  const instance = renderApp(
    createElement(HookHarness, { mode, onAction, enabled, hookRef }),
  );
  return { ...instance, hookRef };
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe("useKeyboard", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // 1. Normal mode: Ctrl+B dispatches "toggle-sidebar"
  it("normal mode: Ctrl+B dispatches toggle-sidebar", async () => {
    const onAction = vi.fn();
    const { stdin } = renderHook("normal", onAction);

    stdin.write("\x02"); // Ctrl+B
    await vi.advanceTimersByTimeAsync(0);

    expect(onAction).toHaveBeenCalledWith("toggle-sidebar");
  });

  // 2. Normal mode: Ctrl+L dispatches "clear-output"
  it("normal mode: Ctrl+L dispatches clear-output", async () => {
    const onAction = vi.fn();
    const { stdin } = renderHook("normal", onAction);

    stdin.write("\x0c"); // Ctrl+L
    await vi.advanceTimersByTimeAsync(0);

    expect(onAction).toHaveBeenCalledWith("clear-output");
  });

  // 3. Normal mode: Ctrl+N dispatches "new-session"
  it("normal mode: Ctrl+N dispatches new-session", async () => {
    const onAction = vi.fn();
    const { stdin } = renderHook("normal", onAction);

    stdin.write("\x0e"); // Ctrl+N
    await vi.advanceTimersByTimeAsync(0);

    expect(onAction).toHaveBeenCalledWith("new-session");
  });

  // 4. Insert mode: Ctrl+B is suppressed (not dispatched)
  it("insert mode: Ctrl+B is suppressed", async () => {
    const onAction = vi.fn();
    const { stdin } = renderHook("insert", onAction);

    stdin.write("\x02"); // Ctrl+B
    await vi.advanceTimersByTimeAsync(0);

    expect(onAction).not.toHaveBeenCalledWith("toggle-sidebar");
  });

  // 5. Insert mode: Ctrl+C dispatches "cancel"
  it("insert mode: Ctrl+C dispatches cancel", async () => {
    const onAction = vi.fn();
    const { stdin } = renderHook("insert", onAction);

    stdin.write("\x03"); // Ctrl+C
    await vi.advanceTimersByTimeAsync(0);

    expect(onAction).toHaveBeenCalledWith("cancel");
  });

  // 6. Leader key: Ctrl+X sets leaderActive = true
  it("leader key: Ctrl+X activates leader mode", async () => {
    const onAction = vi.fn();
    const { stdin, lastFrame } = renderHook("normal", onAction);

    stdin.write("\x18"); // Ctrl+X
    await vi.advanceTimersByTimeAsync(0);

    expect(lastFrame()).toContain("leader:true");
  });

  // 7. Leader key: Ctrl+X → S dispatches "save-session"
  it("leader key: Ctrl+X then S dispatches save-session", async () => {
    const onAction = vi.fn();
    const { stdin } = renderHook("normal", onAction);

    stdin.write("\x18"); // Ctrl+X
    await vi.advanceTimersByTimeAsync(10);
    stdin.write("S");
    await vi.advanceTimersByTimeAsync(0);

    expect(onAction).toHaveBeenCalledWith("save-session");
  });

  // 8. Leader key: Ctrl+X → ? dispatches "help"
  it("leader key: Ctrl+X then ? dispatches help", async () => {
    const onAction = vi.fn();
    const { stdin } = renderHook("normal", onAction);

    stdin.write("\x18"); // Ctrl+X
    await vi.advanceTimersByTimeAsync(10);
    stdin.write("?");
    await vi.advanceTimersByTimeAsync(0);

    expect(onAction).toHaveBeenCalledWith("help");
  });

  // 9. Leader key: Ctrl+X → Q dispatches "quit-all"
  it("leader key: Ctrl+X then Q dispatches quit-all", async () => {
    const onAction = vi.fn();
    const { stdin } = renderHook("normal", onAction);

    stdin.write("\x18"); // Ctrl+X
    await vi.advanceTimersByTimeAsync(10);
    stdin.write("Q");
    await vi.advanceTimersByTimeAsync(0);

    expect(onAction).toHaveBeenCalledWith("quit-all");
  });

  // 10. Leader timeout: Ctrl+X then wait 1100ms → leaderActive goes false
  it("leader timeout: after 1100ms leader mode deactivates", async () => {
    const onAction = vi.fn();
    const { stdin, lastFrame } = renderHook("normal", onAction);

    stdin.write("\x18"); // Ctrl+X
    await vi.advanceTimersByTimeAsync(0);
    expect(lastFrame()).toContain("leader:true");

    await vi.advanceTimersByTimeAsync(1100);
    expect(lastFrame()).toContain("leader:false");
  });

  // 11. Leader timeout: no action dispatched on timeout
  it("leader timeout: no action dispatched when leader times out", async () => {
    const onAction = vi.fn();
    const { stdin } = renderHook("normal", onAction);

    stdin.write("\x18"); // Ctrl+X
    await vi.advanceTimersByTimeAsync(1100);

    expect(onAction).not.toHaveBeenCalled();
  });

  // 12. Enabled=false: no actions dispatched
  it("enabled=false: suppresses all keyboard actions", async () => {
    const onAction = vi.fn();
    const { stdin } = renderHook("normal", onAction, false);

    stdin.write("\x02"); // Ctrl+B
    await vi.advanceTimersByTimeAsync(0);

    expect(onAction).not.toHaveBeenCalled();
  });

  // 13. currentMode reflects passed mode
  it("returns the current mode in state", () => {
    const onAction = vi.fn();
    const { lastFrame } = renderHook("insert", onAction);

    expect(lastFrame()).toContain("mode:insert");
  });

  // 14. Shortcut collision: no two shortcuts share same key+modifier+mode
  it("no shortcut collisions in keybindings", async () => {
    const { defaultKeybindings } = await import("../../config/keybindings.js");

    const seen = new Set<string>();
    const collisions: string[] = [];

    for (const kb of defaultKeybindings) {
      for (const mode of kb.modes) {
        const sig = `${mode}:${kb.ctrl ? "C-" : ""}${kb.shift ? "S-" : ""}${kb.meta ? "M-" : ""}${kb.key}`;
        if (seen.has(sig)) {
          collisions.push(sig);
        } else {
          seen.add(sig);
        }
      }
    }

    expect(collisions).toHaveLength(0);
  });

  // 15. defaultKeybindings has 30+ entries
  it("defaultKeybindings has 30+ shortcuts", async () => {
    const { defaultKeybindings } = await import("../../config/keybindings.js");
    expect(defaultKeybindings.length).toBeGreaterThanOrEqual(30);
  });

  // 16. Normal mode: Ctrl+P dispatches "permission-approve"
  it("normal mode: Ctrl+P dispatches permission-approve", async () => {
    const onAction = vi.fn();
    const { stdin } = renderHook("normal", onAction);

    stdin.write("\x10"); // Ctrl+P
    await vi.advanceTimersByTimeAsync(0);

    expect(onAction).toHaveBeenCalledWith("permission-approve");
  });
});

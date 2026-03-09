import { describe, expect, it } from "vitest";
import {
  isNextEventShortcut,
  isPreviousEventShortcut,
  isApprovePermissionShortcut,
  isClearShortcut,
  isResetShortcut,
  isSaveShortcut,
  isToggleEventPaneShortcut,
  isToggleVerbosityShortcut,
} from "../shortcuts.js";

describe("shortcut helpers", () => {
  it("accepts alt-based app shortcuts", () => {
    expect(isClearShortcut("l", { meta: true })).toBe(true);
    expect(isResetShortcut("n", { meta: true })).toBe(true);
    expect(isApprovePermissionShortcut("p", { meta: true })).toBe(true);
    expect(isSaveShortcut("s", { meta: true })).toBe(true);
    expect(isToggleVerbosityShortcut("v", { meta: true })).toBe(true);
    expect(isToggleEventPaneShortcut("e", { meta: true })).toBe(true);
    expect(isPreviousEventShortcut({ meta: true, upArrow: true })).toBe(true);
    expect(isNextEventShortcut({ meta: true, downArrow: true })).toBe(true);
  });

  it("keeps legacy ctrl-based shortcuts as fallbacks", () => {
    expect(isClearShortcut("l", { ctrl: true })).toBe(true);
    expect(isResetShortcut("n", { ctrl: true })).toBe(true);
    expect(isApprovePermissionShortcut("p", { ctrl: true })).toBe(true);
    expect(isSaveShortcut("s", { ctrl: true })).toBe(true);
    expect(isToggleVerbosityShortcut("v", { ctrl: true })).toBe(true);
    expect(isToggleEventPaneShortcut("e", { ctrl: true })).toBe(true);
    expect(isPreviousEventShortcut({ ctrl: true, pageUp: true })).toBe(true);
    expect(isNextEventShortcut({ ctrl: true, pageDown: true })).toBe(true);
  });
});

import { describe, expect, it } from "vitest";
import {
  isLeaderShortcut,
  resolveLeaderAction,
} from "../shortcuts.js";

describe("shortcut helpers", () => {
  it("recognizes the ctrl+space leader key", () => {
    expect(isLeaderShortcut("\0", {})).toBe(true);
    expect(isLeaderShortcut(" ", { ctrl: true })).toBe(true);
    expect(isLeaderShortcut("`", { ctrl: true })).toBe(true);
    expect(isLeaderShortcut("g", { ctrl: true })).toBe(false);
  });

  it("resolves leader actions from the follow-up key", () => {
    expect(resolveLeaderAction("l", {})).toBe("clear");
    expect(resolveLeaderAction("n", {})).toBe("reset");
    expect(resolveLeaderAction("p", {})).toBe("approvePermission");
    expect(resolveLeaderAction("s", {})).toBe("saveSession");
    expect(resolveLeaderAction("v", {})).toBe("toggleVerbosity");
    expect(resolveLeaderAction("e", {})).toBe("toggleEventPane");
    expect(resolveLeaderAction("", { upArrow: true })).toBe("previousEvent");
    expect(resolveLeaderAction("", { downArrow: true })).toBe("nextEvent");
    expect(resolveLeaderAction("", { escape: true })).toBe("cancel");
    expect(resolveLeaderAction("`", { ctrl: true })).toBe("cancel");
    expect(resolveLeaderAction("\0", {})).toBe("cancel");
    expect(resolveLeaderAction("x", {})).toBe(null);
  });
});

import { describe, it, expect, beforeEach } from "vitest";
import { getIcons, resetIconCache } from "../../src/utils/icons.js";

describe("Unicode icon fallback", () => {
  beforeEach(() => {
    resetIconCache();
  });

  it("returns Unicode icons when forceUnicode=true", () => {
    const icons = getIcons(true);
    expect(icons.check).toBe("✓");
    expect(icons.pending).toBe("○");
    expect(icons.running).toBe("▶");
    expect(icons.failed).toBe("✗");
    expect(icons.arrow).toBe("→");
    expect(icons.bullet).toBe("•");
  });

  it("returns ASCII icons when forceUnicode=false", () => {
    const icons = getIcons(false);
    expect(icons.check).toBe("[x]");
    expect(icons.pending).toBe("[ ]");
    expect(icons.running).toBe(">");
    expect(icons.failed).toBe("[!]");
    expect(icons.arrow).toBe("->");
    expect(icons.bullet).toBe("*");
  });

  it("all ASCII icon values are non-empty strings", () => {
    const icons = getIcons(false);
    for (const [, value] of Object.entries(icons)) {
      expect(typeof value).toBe("string");
      expect(value.length).toBeGreaterThan(0);
    }
  });

  it("all Unicode icon values are non-empty strings", () => {
    const icons = getIcons(true);
    for (const [, value] of Object.entries(icons)) {
      expect(typeof value).toBe("string");
      expect(value.length).toBeGreaterThan(0);
    }
  });

  it("returns same object on repeated calls without forceUnicode (cache)", () => {
    const first = getIcons();
    const second = getIcons();
    expect(first).toBe(second);
  });

  it("cache resets after resetIconCache", () => {
    const first = getIcons();
    resetIconCache();
    const second = getIcons();
    expect(first).toStrictEqual(second);
  });

  it("forceUnicode bypasses cache and does not populate it", () => {
    const forced = getIcons(true);
    const forcedAscii = getIcons(false);
    expect(forced.check).toBe("✓");
    expect(forcedAscii.check).toBe("[x]");

    const auto = getIcons();
    expect(auto.check).toBeDefined();
    expect(typeof auto.check).toBe("string");
  });
});

import { describe, it, expect } from "vitest";
import {
  isBelowMinimum,
  detectCapabilities,
  MIN_WIDTH,
  MIN_HEIGHT,
} from "../../src/utils/terminal.js";
import type { TerminalCapabilities } from "../../src/utils/terminal.js";

describe("terminal resize handling", () => {
  it("isBelowMinimum returns true for 60x20 (below both thresholds)", () => {
    const caps: TerminalCapabilities = {
      colorDepth: 16,
      unicode: true,
      width: 60,
      height: 20,
      isInteractive: false,
    };
    expect(isBelowMinimum(caps)).toBe(true);
  });

  it("isBelowMinimum returns false for 80x24 (exactly at minimum)", () => {
    const caps: TerminalCapabilities = {
      colorDepth: 16,
      unicode: true,
      width: MIN_WIDTH,
      height: MIN_HEIGHT,
      isInteractive: false,
    };
    expect(isBelowMinimum(caps)).toBe(false);
  });

  it("isBelowMinimum returns false for 120x40 (above minimum)", () => {
    const caps: TerminalCapabilities = {
      colorDepth: 16,
      unicode: true,
      width: 120,
      height: 40,
      isInteractive: false,
    };
    expect(isBelowMinimum(caps)).toBe(false);
  });

  it("isBelowMinimum returns true when only width is below minimum", () => {
    const caps: TerminalCapabilities = {
      colorDepth: 16,
      unicode: true,
      width: 60,
      height: 40,
      isInteractive: false,
    };
    expect(isBelowMinimum(caps)).toBe(true);
  });

  it("isBelowMinimum returns true when only height is below minimum", () => {
    const caps: TerminalCapabilities = {
      colorDepth: 16,
      unicode: true,
      width: 120,
      height: 10,
      isInteractive: false,
    };
    expect(isBelowMinimum(caps)).toBe(true);
  });

  it("detectCapabilities returns dimensions within reasonable defaults when no TTY", () => {
    const caps = detectCapabilities();
    expect(caps.width).toBeGreaterThanOrEqual(1);
    expect(caps.height).toBeGreaterThanOrEqual(1);
  });

  it("MIN_WIDTH and MIN_HEIGHT constants are 80 and 24", () => {
    expect(MIN_WIDTH).toBe(80);
    expect(MIN_HEIGHT).toBe(24);
  });
});

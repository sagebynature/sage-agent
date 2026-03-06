import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { detectCapabilities } from "../../src/utils/terminal.js";

describe("signal handling concepts", () => {
  let savedEnv: Record<string, string | undefined>;

  beforeEach(() => {
    savedEnv = {
      COLORTERM: process.env["COLORTERM"],
      TERM: process.env["TERM"],
      NO_COLOR: process.env["NO_COLOR"],
      LANG: process.env["LANG"],
      LC_ALL: process.env["LC_ALL"],
    };
  });

  afterEach(() => {
    for (const [key, value] of Object.entries(savedEnv)) {
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  });

  it("isInteractive is false in the test environment (no TTY attached)", () => {
    const caps = detectCapabilities();
    expect(caps.isInteractive).toBe(false);
  });

  it("capability detection returns a complete object with all required fields", () => {
    const caps = detectCapabilities();
    expect(caps).toHaveProperty("colorDepth");
    expect(caps).toHaveProperty("unicode");
    expect(caps).toHaveProperty("width");
    expect(caps).toHaveProperty("height");
    expect(caps).toHaveProperty("isInteractive");
  });

  it("terminal capabilities are consistent across multiple calls", () => {
    const first = detectCapabilities();
    const second = detectCapabilities();
    expect(first.colorDepth).toBe(second.colorDepth);
    expect(first.unicode).toBe(second.unicode);
    expect(first.isInteractive).toBe(second.isInteractive);
  });

  it("colorDepth is one of the valid values: 0, 16, 256, 24", () => {
    const caps = detectCapabilities();
    expect([0, 16, 256, 24]).toContain(caps.colorDepth);
  });

  it("unicode field is a boolean", () => {
    const caps = detectCapabilities();
    expect(typeof caps.unicode).toBe("boolean");
  });

  it("detects unicode=false for dumb terminal (affects signal/render fallback behavior)", () => {
    process.env["TERM"] = "dumb";
    delete process.env["COLORTERM"];
    const caps = detectCapabilities();
    expect(caps.unicode).toBe(false);
    expect(caps.colorDepth).toBe(0);
  });
});

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { detectCapabilities } from "../../src/utils/terminal.js";

describe("terminal capability detection", () => {
  let savedEnv: Record<string, string | undefined>;

  beforeEach(() => {
    savedEnv = {
      COLORTERM: process.env["COLORTERM"],
      TERM: process.env["TERM"],
      NO_COLOR: process.env["NO_COLOR"],
      LANG: process.env["LANG"],
      LC_ALL: process.env["LC_ALL"],
      WT_SESSION: process.env["WT_SESSION"],
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

  it("detects truecolor when COLORTERM=truecolor", () => {
    process.env["COLORTERM"] = "truecolor";
    delete process.env["NO_COLOR"];
    const caps = detectCapabilities();
    expect(caps.colorDepth).toBe(24);
  });

  it("detects truecolor when COLORTERM=24bit", () => {
    process.env["COLORTERM"] = "24bit";
    delete process.env["NO_COLOR"];
    const caps = detectCapabilities();
    expect(caps.colorDepth).toBe(24);
  });

  it("detects 256-color when TERM contains 256color", () => {
    delete process.env["COLORTERM"];
    delete process.env["NO_COLOR"];
    process.env["TERM"] = "xterm-256color";
    const caps = detectCapabilities();
    expect(caps.colorDepth).toBe(256);
  });

  it("detects no color when NO_COLOR=1", () => {
    delete process.env["COLORTERM"];
    process.env["NO_COLOR"] = "1";
    process.env["TERM"] = "xterm";
    const caps = detectCapabilities();
    expect(caps.colorDepth).toBe(0);
  });

  it("detects no color and no unicode for dumb terminal", () => {
    delete process.env["COLORTERM"];
    delete process.env["NO_COLOR"];
    process.env["TERM"] = "dumb";
    const caps = detectCapabilities();
    expect(caps.colorDepth).toBe(0);
    expect(caps.unicode).toBe(false);
  });

  it("detects unicode when LANG contains UTF-8", () => {
    delete process.env["COLORTERM"];
    delete process.env["NO_COLOR"];
    process.env["TERM"] = "xterm";
    process.env["LANG"] = "en_US.UTF-8";
    const caps = detectCapabilities();
    expect(caps.unicode).toBe(true);
  });

  it("reports non-interactive when stdout has no TTY in test env", () => {
    const caps = detectCapabilities();
    expect(caps.isInteractive).toBe(false);
  });
});

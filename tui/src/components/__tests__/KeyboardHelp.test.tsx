import { describe, it, expect, vi } from "vitest";
import { createElement } from "react";
import { renderApp } from "../../test-utils.js";
import { KeyboardHelp } from "../KeyboardHelp.js";

describe("KeyboardHelp", () => {
  it("renders nothing when visible=false", () => {
    const onClose = vi.fn();
    const { lastFrame } = renderApp(
      createElement(KeyboardHelp, { visible: false, onClose }),
    );
    expect(lastFrame()).not.toContain("Keyboard Shortcuts");
  });

  it("renders overlay when visible=true", () => {
    const onClose = vi.fn();
    const { lastFrame } = renderApp(
      createElement(KeyboardHelp, { visible: true, onClose }),
    );
    expect(lastFrame()).toContain("Keyboard Shortcuts");
  });

  it("displays all 6 category headers", () => {
    const onClose = vi.fn();
    const { lastFrame } = renderApp(
      createElement(KeyboardHelp, { visible: true, onClose }),
    );
    const frame = lastFrame() ?? "";
    expect(frame).toContain("Navigation");
    expect(frame).toContain("Session");
    expect(frame).toContain("View");
    expect(frame).toContain("Input");
    expect(frame).toContain("Agent");
    expect(frame).toContain("Leader");
  });

  it("displays at least 30 shortcuts in overlay", () => {
    const onClose = vi.fn();
    const { lastFrame } = renderApp(
      createElement(KeyboardHelp, { visible: true, onClose }),
    );
    const frame = lastFrame() ?? "";
    const lines = frame.split("\n").filter((l) => l.trim().length > 0);
    expect(lines.length).toBeGreaterThanOrEqual(30);
  });

  it("shows close hint", () => {
    const onClose = vi.fn();
    const { lastFrame } = renderApp(
      createElement(KeyboardHelp, { visible: true, onClose }),
    );
    const frame = lastFrame() ?? "";
    expect(frame).toMatch(/close|ESC|press/i);
  });
});

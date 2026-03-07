import { describe, it, expect } from "vitest";
import { App } from "../App.js";
import { renderApp } from "../../test-utils.js";

describe("App Shell", () => {
  it("renders main layout with input prompt and bottom bar", () => {
    const { lastFrame } = renderApp(<App />);
    const frame = lastFrame();
    expect(frame).toContain(">");
    expect(frame).toContain("no model");
  });

  it("renders divider lines", () => {
    const { lastFrame } = renderApp(<App />);
    expect(lastFrame()).toContain("─");
  });

  it("shows context usage bar", () => {
    const { lastFrame } = renderApp(<App />);
    expect(lastFrame()).toContain("0%");
  });
});

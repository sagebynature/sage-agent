import { describe, it, expect } from "vitest";
import { renderApp } from "./test-utils.js";
import { App } from "./App.js";

describe("App", () => {
  it("renders without crashing", () => {
    const { lastFrame } = renderApp(<App />);
    expect(lastFrame()).toBeTruthy();
  });

  it("displays sage-tui text", () => {
    const { lastFrame } = renderApp(<App />);
    expect(lastFrame()).toContain("sage-tui");
  });

  it("displays welcome message", () => {
    const { lastFrame } = renderApp(<App />);
    expect(lastFrame()).toContain("Welcome");
  });
});

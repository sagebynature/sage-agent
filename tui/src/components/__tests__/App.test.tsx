import { describe, it, expect } from "vitest";
import { App } from "../App.js";
import { renderApp, waitForText } from "../../test-utils.js";

describe("App Shell", () => {
  it("renders main layout with header and footer", () => {
    const { lastFrame } = renderApp(<App />);
    const frame = lastFrame();
    expect(frame).toContain("sage-tui");
    expect(frame).toContain("Ctrl+B");
  });

  it("renders welcome message when no messages", () => {
    const { lastFrame } = renderApp(<App />);
    expect(lastFrame()).toContain("Welcome");
  });

  it("starts in focused view mode", () => {
    const { lastFrame } = renderApp(<App />);
    expect(lastFrame()).not.toContain("Sidebar");
  });

  it("toggles to split view on Ctrl+B", async () => {
    const instance = renderApp(<App />);
    instance.stdin.write("\x02");
    await waitForText(instance, "Sidebar");
  });

  it("toggles back to focused on second Ctrl+B", async () => {
    const instance = renderApp(<App />);
    instance.stdin.write("\x02");
    await waitForText(instance, "Sidebar");
    instance.stdin.write("\x02");
    await new Promise(r => setTimeout(r, 100));
    expect(instance.lastFrame()).not.toContain("Sidebar");
  });

  it("shows streaming indicator in footer when streaming", () => {
    const { lastFrame } = renderApp(<App />);
    expect(lastFrame()).toContain("Ctrl+C quit");
  });
});

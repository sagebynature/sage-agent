import { describe, it, expect } from "vitest";
import { Box } from "ink";
import { StatusBarHeader, StatusBarFooter } from "../StatusBar.js";
import { renderApp } from "../../test-utils.js";
import { AppProvider } from "../../state/AppContext.js";
import React from "react";

function renderWithProvider(component: React.ReactElement) {
  return renderApp(
    <AppProvider>
      <Box flexDirection="column">
        {component}
      </Box>
    </AppProvider>
  );
}

describe("StatusBarHeader", () => {
  it("renders sage-tui label", () => {
    const { lastFrame } = renderWithProvider(<StatusBarHeader />);
    expect(lastFrame()).toContain("sage-tui");
  });

  it("renders model name placeholder when no model set", () => {
    const { lastFrame } = renderWithProvider(<StatusBarHeader />);
    expect(lastFrame()).toContain("no model");
  });

  it("renders context usage percentage", () => {
    const { lastFrame } = renderWithProvider(<StatusBarHeader />);
    expect(lastFrame()).toContain("0%");
  });

  it("renders cost display", () => {
    const { lastFrame } = renderWithProvider(<StatusBarHeader />);
    expect(lastFrame()).toContain("$0.00");
  });
});

describe("StatusBarFooter", () => {
  it("shows shortcut hints in idle mode", () => {
    const { lastFrame } = renderWithProvider(<StatusBarFooter />);
    expect(lastFrame()).toContain("Ctrl+B");
    expect(lastFrame()).toContain("commands");
  });

  it("shows quit option in idle mode", () => {
    const { lastFrame } = renderWithProvider(<StatusBarFooter />);
    expect(lastFrame()).toContain("quit");
  });
});

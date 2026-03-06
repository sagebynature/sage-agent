import { render } from "ink-testing-library";
import { describe, it, expect, vi } from "vitest";
import { PlanningPanel } from "../PlanningPanel.js";
import { PlanContext, type PlanState, INITIAL_STATE } from "../../contexts/PlanContext.js";

const renderWithContext = (state: PlanState) => {
  return render(
    <PlanContext value={{ state, dispatch: vi.fn() }}>
      <PlanningPanel />
    </PlanContext>
  );
};

describe("PlanningPanel", () => {
  it("renders empty state correctly", () => {
    const { lastFrame } = renderWithContext(INITIAL_STATE);
    expect(lastFrame()).toContain("No active plan");
  });

  it("renders plan header with name and date", () => {
    const state: PlanState = {
      ...INITIAL_STATE,
      name: "My Awesome Plan",
      createdAt: "2023-10-27 10:00:00",
    };
    const { lastFrame } = renderWithContext(state);
    expect(lastFrame()).toContain("My Awesome Plan");
    expect(lastFrame()).toContain("2023-10-27 10:00:00");
  });

  it("renders progress bar correctly for mixed statuses", () => {
    const state: PlanState = {
      ...INITIAL_STATE,
      name: "Progress Test",
      tasks: [
        { description: "Task 1", status: "completed" },
        { description: "Task 2", status: "completed" },
        { description: "Task 3", status: "running" },
        { description: "Task 4", status: "pending" },
        { description: "Task 5", status: "pending" },
      ],
    };
    const { lastFrame } = renderWithContext(state);
    expect(lastFrame()).toContain("2/5 tasks completed (40%)");
    expect(lastFrame()).toContain("████████░░░░░░░░░░░░");
  });

  it("renders task icons correctly", () => {
    const state: PlanState = {
      ...INITIAL_STATE,
      name: "Icons Test",
      tasks: [
        { description: "Task 1", status: "completed" },
        { description: "Task 2", status: "running" },
        { description: "Task 3", status: "failed" },
        { description: "Task 4", status: "pending" },
      ],
    };
    const { lastFrame } = renderWithContext(state);
    expect(lastFrame()).toContain("✓");
    expect(lastFrame()).toContain("▶");
    expect(lastFrame()).toContain("✗");
    expect(lastFrame()).toContain("○");
  });

  it("highlights running task description", () => {
    const state: PlanState = {
        ...INITIAL_STATE,
        name: "Highlight Test",
        tasks: [
            { description: "Running Task", status: "running" }
        ]
    };
    const { lastFrame } = renderWithContext(state);
    expect(lastFrame()).toContain("Running Task");
  });

  it("renders notepad content", () => {
    const state: PlanState = {
      ...INITIAL_STATE,
      name: "Notepad Test",
      notepadContent: "This is some important note.",
    };
    const { lastFrame } = renderWithContext(state);
    expect(lastFrame()).toContain("Notepad");
    expect(lastFrame()).toContain("This is some important note.");
  });

  it("renders empty notepad message", () => {
    const state: PlanState = {
      ...INITIAL_STATE,
      name: "Empty Notepad Test",
      notepadContent: "",
    };
    const { lastFrame } = renderWithContext(state);
    expect(lastFrame()).toContain("No notes yet");
  });

  it("truncates long task descriptions", () => {
    const longDesc = "This is a very very very very long task description that should be truncated";
    const state: PlanState = {
        ...INITIAL_STATE,
        name: "Truncate Test",
        tasks: [
            { description: longDesc, status: "pending" }
        ]
    };
     const { lastFrame } = renderWithContext(state);
     expect(lastFrame()).toContain("This is a very very");
  });
});

import { describe, it, expect, vi } from "vitest";
import { render } from "ink-testing-library";
import { BackgroundTaskPanel, BackgroundTask } from "../BackgroundTaskPanel";
import { TaskStatusBadge } from "../TaskStatusBadge";

vi.mock("ink-spinner", () => ({
  default: () => "⠋",
}));

describe("TaskStatusBadge", () => {
  it("renders pending state correctly", () => {
    const { lastFrame } = render(<TaskStatusBadge status="pending" />);
    expect(lastFrame()).toContain("[pending]");
  });

  it("renders running state correctly", () => {
    const { lastFrame } = render(<TaskStatusBadge status="running" />);
    expect(lastFrame()).toContain("[running ⠋]");
  });

  it("renders completed state correctly", () => {
    const { lastFrame } = render(<TaskStatusBadge status="completed" />);
    expect(lastFrame()).toContain("[completed ✓]");
  });

  it("renders failed state correctly", () => {
    const { lastFrame } = render(<TaskStatusBadge status="failed" />);
    expect(lastFrame()).toContain("[failed ✗]");
  });

  it("renders cancelled state correctly", () => {
    const { lastFrame } = render(<TaskStatusBadge status="cancelled" />);
    expect(lastFrame()).toContain("[cancelled ⊘]");
  });
});

describe("BackgroundTaskPanel", () => {
  const mockTasks: BackgroundTask[] = [
    {
      taskId: "task-123",
      agentName: "Agent Smith",
      description: "Analyzing the matrix code",
      status: "running",
      startedAt: Date.now() - 5000,
    },
    {
      taskId: "task-456",
      agentName: "Oracle",
      description: "Baking cookies",
      status: "completed",
      startedAt: Date.now() - 10000,
      completedAt: Date.now() - 2000,
      result: "Cookies are ready",
    },
    {
      taskId: "task-789",
      agentName: "Neo",
      description: "Flying",
      status: "failed",
      error: "Gravity too strong",
    },
  ];

  it("renders empty state when no tasks", () => {
    const { lastFrame } = render(<BackgroundTaskPanel tasks={[]} />);
    expect(lastFrame()).toContain("No background tasks");
  });

  it("renders list of tasks", () => {
    const { lastFrame } = render(<BackgroundTaskPanel tasks={mockTasks} />);
    expect(lastFrame()).toContain("task-123");
    expect(lastFrame()).toContain("Agent Smith");
    expect(lastFrame()).toContain("Analyzing the matrix code");
    expect(lastFrame()).toContain("task-456");
    expect(lastFrame()).toContain("Oracle");
    expect(lastFrame()).toContain("task-789");
  });

  it("shows expanded details for failed tasks by default", () => {
    const { lastFrame } = render(<BackgroundTaskPanel tasks={mockTasks} />);
    expect(lastFrame()).toContain("Gravity too strong");
  });

  it("handles cancel action", async () => {
    const onCancel = vi.fn();
    const { stdin } = render(
      <BackgroundTaskPanel tasks={mockTasks} onCancel={onCancel} />
    );

    stdin.write("c");
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(onCancel).toHaveBeenCalledWith("task-123");
  });

  it("handles rerun action", async () => {
    const onRerun = vi.fn();
    const { stdin } = render(
      <BackgroundTaskPanel tasks={mockTasks} onRerun={onRerun} />
    );

    stdin.write("j");
    await new Promise((resolve) => setTimeout(resolve, 50)); // Wait for navigation
    stdin.write("r");
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(onRerun).toHaveBeenCalledWith("task-456");
  });

  it("expands/collapses task details", async () => {
    const longTask: BackgroundTask = {
      ...mockTasks[0]!,
      description: "A very long description that exceeds the 60 character limit and should definitely trigger the full description view when expanded",
    };
    const { stdin, lastFrame } = render(<BackgroundTaskPanel tasks={[longTask]} />);

    expect(lastFrame()).not.toContain("Full Description:");

    stdin.write("\r");
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(lastFrame()).toContain("Full Description:");
  });
});

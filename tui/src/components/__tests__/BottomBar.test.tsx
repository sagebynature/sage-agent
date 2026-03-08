import { render } from "ink-testing-library";
import { describe, expect, it } from "vitest";
import { BottomBar } from "../BottomBar.js";

describe("BottomBar", () => {
  it("renders repo context on the first line and runtime state on the second", () => {
    const { lastFrame } = render(
      <BottomBar
        width={60}
        cwd="~/workspace/sage-agent"
        gitBranch="main"
        usage={{
          promptTokens: 0,
          completionTokens: 0,
          totalCost: 0,
          model: "openrouter/openrouter/free",
          contextUsagePercent: 3,
        }}
        activeStream={{ runId: "2861764d-long-run-id", content: "", tools: [], isThinking: false, startedAt: Date.now() }}
        permissions={[]}
        error={null}
        connectionStatus="connected"
        agents={[
          { name: "orchestrator", status: "active", depth: 0, children: [] },
          { name: "researcher", status: "active", depth: 1, children: [] },
        ]}
        sessionName="orchestrator"
        modelName="openrouter/openrouter/free"
        verbosity="compact"
        showEventPane
        activeRun={{
          runId: "2861764d-long-run-id",
          status: "running",
          agentPath: ["orchestrator"],
          agentName: "orchestrator",
          startedAt: Date.now(),
        }}
        selectedEvent={{
          id: "event-1",
          eventName: "pre_llm_call",
          category: "llm",
          phase: "start",
          timestamp: Date.now(),
          agentName: "orchestrator",
          agentPath: ["orchestrator"],
          payload: {},
          summary: "turn started",
        }}
      />,
    );

    const lines = (lastFrame() ?? "").split("\n");

    expect(lines).toHaveLength(2);
    expect(lines[0]).toContain("~/workspace/sage-agent");
    expect(lines[0]).toContain("main");
    expect(lines[0]).toContain("orchestrator");
    expect(lines[1]).toContain("streaming");
    expect(lines[1]).toContain("3% used");
    expect(lines[1]).toContain("$0.00");
  });

  it("omits the branch segment when no repo context is available", () => {
    const { lastFrame } = render(
      <BottomBar
        width={60}
        cwd="~/workspace/sage-agent"
        gitBranch=""
        usage={{
          promptTokens: 0,
          completionTokens: 0,
          totalCost: 0,
          model: "openrouter/openrouter/free",
          contextUsagePercent: 3,
        }}
        activeStream={null}
        permissions={[]}
        error={null}
        connectionStatus="connected"
        agents={[]}
        sessionName="orchestrator"
        modelName="openrouter/openrouter/free"
        verbosity="compact"
        showEventPane={false}
      />,
    );

    const firstLine = (lastFrame() ?? "").split("\n")[0] ?? "";
    expect(firstLine).toContain("~/workspace/sage-agent");
    expect(firstLine).not.toContain("git");
  });
});

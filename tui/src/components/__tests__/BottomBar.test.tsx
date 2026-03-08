import { render } from "ink-testing-library";
import { describe, expect, it } from "vitest";
import { BottomBar } from "../BottomBar.js";

describe("BottomBar", () => {
  it("truncates to a single line on narrow widths", () => {
    const { lastFrame } = render(
      <BottomBar
        width={60}
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

    expect((lastFrame() ?? "").split("\n")).toHaveLength(1);
  });
});

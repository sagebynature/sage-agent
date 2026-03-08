import { describe, it, expect, vi } from "vitest";
import { App } from "../App.js";
import { renderApp, waitForText } from "../../test-utils.js";

const mockRequest = vi.hoisted(() =>
  vi.fn(async (method: string, params?: Record<string, unknown>) => {
    if (method === "config/get" && params?.key === "name") {
      return { key: "name", value: "test-agent" };
    }
    if (method === "config/get" && params?.key === "model") {
      return { key: "model", value: "gpt-4o" };
    }
    return {};
  }),
);

vi.mock("../../ipc/client.js", async () => {
  const { EventEmitter } = await import("node:events");

  class MockSageClient extends EventEmitter {
    status = "connected" as const;

    async spawn(): Promise<void> {}

    async request<T = unknown>(method: string, params?: Record<string, unknown>): Promise<T> {
      return mockRequest(method, params) as Promise<T>;
    }

    onNotification(): () => void {
      return () => {};
    }

    dispose(): void {}
  }

  return { SageClient: MockSageClient };
});

describe("App Shell", () => {
  it("renders main layout with input prompt and bottom bar", () => {
    const { lastFrame } = renderApp(<App />);
    const frame = lastFrame();
    expect(frame).toContain(">");
  });

  it("renders divider lines", () => {
    const { lastFrame } = renderApp(<App />);
    expect(lastFrame()).toContain("─");
  });

  it("shows context usage bar", () => {
    const { lastFrame } = renderApp(<App />);
    expect(lastFrame()).toContain("0%");
  });

  it("shows the current main agent and model in the bottom bar", async () => {
    const app = renderApp(<App />);
    await waitForText(app, "test-agent");
    expect(app.lastFrame()).toContain("test-agent");
    expect(app.lastFrame()).toContain("gpt-4o");
    expect(app.lastFrame()).not.toContain("no model");
  });
});

import { describe, it, expect, vi } from "vitest";
import { renderApp, waitForText } from "./test-utils.js";

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

vi.mock("./ipc/client.js", async () => {
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

import { App } from "./App.js";

describe("App", () => {
  it("renders without crashing", () => {
    const { lastFrame } = renderApp(<App />);
    expect(lastFrame()).toBeTruthy();
  });

  it("displays input prompt", () => {
    const { lastFrame } = renderApp(<App />);
    expect(lastFrame()).toContain(">");
  });

  it("displays bottom bar with the current main agent and model", async () => {
    const app = renderApp(<App />);
    await waitForText(app, "test-agent");
    expect(app.lastFrame()).toContain("test-agent");
    expect(app.lastFrame()).toContain("gpt-4o");
    expect(app.lastFrame()).not.toContain("no model");
  });
});

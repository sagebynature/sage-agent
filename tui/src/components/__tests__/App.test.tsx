import { beforeEach, describe, it, expect, vi } from "vitest";
import { App } from "../App.js";
import { renderApp, waitForText } from "../../test-utils.js";
import { METHODS } from "../../types/protocol.js";

vi.mock("../../hooks/useResizeHandler.js", () => ({
  useResizeHandler: () => ({ width: 160, height: 40 }),
}));

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
const notificationHandlers = vi.hoisted(
  () => new Map<string, Set<(params: Record<string, unknown>) => void>>(),
);

vi.mock("../../ipc/client.js", async () => {
  const { EventEmitter } = await import("node:events");

  class MockSageClient extends EventEmitter {
    status = "connected" as const;

    async spawn(): Promise<void> {}

    async request<T = unknown>(method: string, params?: Record<string, unknown>): Promise<T> {
      return mockRequest(method, params) as Promise<T>;
    }

    onNotification(method: string, callback: (params: Record<string, unknown>) => void): () => void {
      const handlers = notificationHandlers.get(method) ?? new Set();
      handlers.add(callback);
      notificationHandlers.set(method, handlers);

      return () => {
        const current = notificationHandlers.get(method);
        current?.delete(callback);
        if (current && current.size === 0) {
          notificationHandlers.delete(method);
        }
      };
    }

    dispose(): void {}
  }

  return { SageClient: MockSageClient };
});

function emitNotification(method: string, params: Record<string, unknown>): void {
  const handlers = notificationHandlers.get(method);
  if (!handlers) {
    return;
  }

  for (const handler of handlers) {
    handler(params);
  }
}

describe("App Shell", () => {
  beforeEach(() => {
    mockRequest.mockClear();
    notificationHandlers.clear();
  });

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

  it("cycles prompt history with up/down arrows in the app shell", async () => {
    const app = renderApp(<App />);

    app.stdin.write("first");
    await new Promise((resolve) => setTimeout(resolve, 20));
    app.stdin.write("\r");
    await new Promise((resolve) => setTimeout(resolve, 20));

    app.stdin.write("second");
    await new Promise((resolve) => setTimeout(resolve, 20));
    app.stdin.write("\r");
    await new Promise((resolve) => setTimeout(resolve, 20));

    app.stdin.write("\u001B[A");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(app.lastFrame() ?? "").toContain("second");

    app.stdin.write("\u001B[A");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(app.lastFrame() ?? "").toContain("first");

    app.stdin.write("\u001B[B");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(app.lastFrame() ?? "").toContain("second");
  });

  it("supports ctrl+space leader shortcuts for terminal-safe controls", async () => {
    const app = renderApp(<App />);

    expect(app.lastFrame() ?? "").toContain("compact");
    expect(app.lastFrame() ?? "").not.toContain(" | leader");

    app.stdin.write("\u0000");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(app.lastFrame() ?? "").toContain(" | leader");

    app.stdin.write("v");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(app.lastFrame() ?? "").toContain("normal");
    expect(app.lastFrame() ?? "").not.toContain("> v");

    app.stdin.write("\u0000");
    await new Promise((resolve) => setTimeout(resolve, 20));
    app.stdin.write("e");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(app.lastFrame() ?? "").not.toContain("normal+events | leader");
  });

  it("cancels leader mode on escape without mutating the prompt", async () => {
    const app = renderApp(<App />);

    app.stdin.write("\u0000");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(app.lastFrame() ?? "").toContain(" | leader");

    app.stdin.write("\u001B");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(app.lastFrame() ?? "").not.toContain(" | leader");

    app.stdin.write("v");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(app.lastFrame() ?? "").toContain("> v");
  });

  it("renders only the first pending permission prompt and queues the rest", async () => {
    const app = renderApp(<App />);

    emitNotification(METHODS.PERMISSION_REQUEST, {
      request_id: "perm-1",
      tool: "file_read",
      arguments: { path: "one.txt" },
      riskLevel: "low",
    });
    emitNotification(METHODS.PERMISSION_REQUEST, {
      request_id: "perm-2",
      tool: "file_write",
      arguments: { path: "two.txt" },
      riskLevel: "high",
    });

    await new Promise((resolve) => setTimeout(resolve, 20));

    const frame = app.lastFrame() ?? "";
    expect(frame).toContain("file_read");
    expect(frame).not.toContain("file_write");
    expect(frame).toContain("1 more permission request queued");
  });
});

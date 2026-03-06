import { describe, it, expect } from "vitest";
import { ChatView } from "../ChatView.js";
import { MessageBubble } from "../MessageBubble.js";
import { renderApp } from "../../test-utils.js";
import { AppProvider } from "../../state/AppContext.js";
import type { ChatMessage } from "../../types/state.js";

function renderChatView() {
  return renderApp(
    <AppProvider>
      <ChatView />
    </AppProvider>
  );
}

describe("ChatView", () => {
  it("renders welcome screen when no messages", () => {
    const { lastFrame } = renderChatView();
    const frame = lastFrame() ?? "";
    expect(frame).toContain("WELCOME TO SAGE-TUI");
  });

  it("shows quick-start tips in welcome screen", () => {
    const { lastFrame } = renderChatView();
    const frame = lastFrame() ?? "";
    expect(frame).toContain("Get started");
    expect(frame).toContain("/help");
  });

  it("renders sage branding in welcome screen", () => {
    const { lastFrame } = renderChatView();
    const frame = lastFrame() ?? "";
    expect(frame).toContain("SAGE-TUI");
  });
});

describe("MessageBubble", () => {
  const baseMessage: ChatMessage = {
    id: "msg-1",
    role: "user",
    content: "Hello world",
    timestamp: Date.now(),
    isStreaming: false,
  };

  it("renders user message with user label", () => {
    const { lastFrame } = renderApp(
      <MessageBubble message={baseMessage} />
    );
    const frame = lastFrame() ?? "";
    expect(frame).toContain("[You]");
    expect(frame).toContain("Hello world");
  });

  it("renders assistant message with sage label", () => {
    const { lastFrame } = renderApp(
      <MessageBubble message={{ ...baseMessage, role: "assistant", content: "Hi there" }} />
    );
    const frame = lastFrame() ?? "";
    expect(frame).toContain("[Sage]");
    expect(frame).toContain("Hi there");
  });

  it("shows streaming indicator for streaming message", () => {
    const { lastFrame } = renderApp(
      <MessageBubble message={{ ...baseMessage, role: "assistant", content: "Thinking...", isStreaming: true }} />
    );
    const frame = lastFrame() ?? "";
    expect(frame).toContain("⠙");
  });

  it("renders system message with dimmed italic style", () => {
    const { lastFrame } = renderApp(
      <MessageBubble message={{ ...baseMessage, role: "system", content: "Session started" }} />
    );
    const frame = lastFrame() ?? "";
    expect(frame).toContain("Session started");
  });

  it("truncates very long messages", () => {
    const longContent = "x".repeat(3000);
    const { lastFrame } = renderApp(
      <MessageBubble message={{ ...baseMessage, content: longContent }} />
    );
    const frame = lastFrame() ?? "";
    expect(frame).toContain("truncated");
    expect(frame).toContain("3000 chars");
  });

  it("shows relative timestamp", () => {
    const { lastFrame } = renderApp(
      <MessageBubble message={{ ...baseMessage, timestamp: Date.now() }} />
    );
    const frame = lastFrame() ?? "";
    expect(frame).toContain("just now");
  });
});

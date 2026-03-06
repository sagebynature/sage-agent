import { describe, it, expect, vi } from "vitest";
import { InputArea } from "../InputArea.js";
import { renderApp } from "../../test-utils.js";
import { AppProvider } from "../../state/AppContext.js";

function renderInputArea(props = {}) {
  return renderApp(
    <AppProvider>
      <InputArea {...props} />
    </AppProvider>
  );
}

describe("InputArea", () => {
  it("renders input prompt", () => {
    const { lastFrame } = renderInputArea();
    expect(lastFrame()).toContain(">");
  });

  it("renders placeholder text", () => {
    const { lastFrame } = renderInputArea();
    expect(lastFrame()).toContain("Type your message");
  });

  it("calls onSubmit when Enter pressed", async () => {
    const onSubmit = vi.fn();
    const { stdin } = renderInputArea({ onSubmit });
    stdin.write("hello world");
    await new Promise(r => setTimeout(r, 10));
    stdin.write("\r");
    await new Promise(r => setTimeout(r, 10));
    expect(onSubmit).toHaveBeenCalledWith("hello world");
  });

  it("clears input after submit", async () => {
    const onSubmit = vi.fn();
    const { stdin, lastFrame } = renderInputArea({ onSubmit });
    stdin.write("hello");
    await new Promise(r => setTimeout(r, 10));
    stdin.write("\r");
    await new Promise(r => setTimeout(r, 10));
    expect(lastFrame()).not.toContain("hello");
  });

  it("shows command mode for / prefix", async () => {
    const { stdin, lastFrame } = renderInputArea();
    stdin.write("/");
    await new Promise(r => setTimeout(r, 50));
    const frame = lastFrame() ?? "";
    expect(frame).toContain("[Command]");
  });

  it("shows shell mode for ! prefix", async () => {
    const { stdin, lastFrame } = renderInputArea();
    stdin.write("!");
    await new Promise(r => setTimeout(r, 50));
    const frame = lastFrame() ?? "";
    expect(frame).toContain("[Shell]");
  });

  it("shows character count when text present", async () => {
    const { stdin, lastFrame } = renderInputArea();
    stdin.write("hello");
    await new Promise(r => setTimeout(r, 10));
    expect(lastFrame()).toContain("5 chars");
  });

  it("returns to normal mode on Escape", async () => {
    const { stdin, lastFrame } = renderInputArea();
    stdin.write("/");
    await new Promise(r => setTimeout(r, 50));
    expect(lastFrame()).toMatch(/Command/);
    stdin.write("\x1B");
    await new Promise(r => setTimeout(r, 50));
    expect(lastFrame()).not.toContain("[Command]");
  });
});

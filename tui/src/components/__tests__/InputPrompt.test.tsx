import { describe, expect, it, vi } from "vitest";
import { render } from "ink-testing-library";
import { InputPrompt } from "../InputPrompt.js";

describe("InputPrompt", () => {
  it("does not leak ctrl shortcuts into the text input", () => {
    vi.useFakeTimers();

    const { stdin, lastFrame } = render(
      <InputPrompt
        onSubmit={() => { }}
        onCommand={() => { }}
        isActive
        width={80}
      />,
    );

    stdin.write("\u000b");
    vi.runAllTimers();

    expect(lastFrame() ?? "").not.toContain("> j");
    vi.useRealTimers();
  });

  it("inserts a newline with ctrl+j without submitting", () => {
    vi.useFakeTimers();

    const onSubmit = vi.fn();
    const { stdin, lastFrame } = render(
      <InputPrompt
        onSubmit={onSubmit}
        onCommand={() => { }}
        isActive
        width={80}
      />,
    );

    stdin.write("\u000b");
    vi.runAllTimers();

    expect(onSubmit).not.toHaveBeenCalled();
    expect(lastFrame() ?? "").not.toContain("> j");
    vi.useRealTimers();
  });
});

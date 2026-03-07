import { describe, expect, it } from "vitest";
import { MarkdownRenderer, renderMarkdown, stripHtml, withClosedCodeFence } from "../MarkdownRenderer.js";
import { renderApp } from "../../test-utils.js";

describe("MarkdownRenderer", () => {
  it("renders headings", () => {
    const { lastFrame } = renderApp(<MarkdownRenderer content="# Title" />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("# Title");
  });

  it("renders bold and italic text", () => {
    const { lastFrame } = renderApp(<MarkdownRenderer content="**bold** and *italic*" />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("bold");
    expect(frame).toContain("italic");
  });

  it("renders inline code", () => {
    const { lastFrame } = renderApp(<MarkdownRenderer content="Use `pnpm test` here" />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("pnpm test");
  });

  it("renders fenced code blocks with language label", () => {
    const markdown = "```ts\nconst x: number = 1;\n```";
    const { lastFrame } = renderApp(<MarkdownRenderer content={markdown} />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("[TYPESCRIPT]");
    expect(frame).toContain("const x");
  });

  it("renders unordered lists", () => {
    const { lastFrame } = renderApp(<MarkdownRenderer content="- one\n- two" />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("one");
    expect(frame).toContain("two");
  });

  it("renders blockquotes", () => {
    const { lastFrame } = renderApp(<MarkdownRenderer content="> quoted" />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("quoted");
  });

  it("renders tables", () => {
    const markdown = "| a | b |\n|---|---|\n| 1 | 2 |";
    const { lastFrame } = renderApp(<MarkdownRenderer content={markdown} />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("a");
    expect(frame).toContain("b");
    expect(frame).toContain("1");
    expect(frame).toContain("2");
  });

  it("renders horizontal rules", () => {
    const { lastFrame } = renderApp(<MarkdownRenderer content="top\n\n---\n\nbottom" />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("top");
    expect(frame).toContain("bottom");
    expect(frame).toContain("---");
  });

  it("renders links as text and href", () => {
    const { lastFrame } = renderApp(
      <MarkdownRenderer content="[Sage](https://example.com/docs)" />,
    );
    const frame = lastFrame() ?? "";
    expect(frame).toContain("Sage");
    expect(frame).toContain("example.com/docs");
  });

  it("strips HTML from input", () => {
    const { lastFrame } = renderApp(
      <MarkdownRenderer content="safe <script>alert('x')</script> content" />,
    );
    const frame = lastFrame() ?? "";
    expect(frame).toContain("safe");
    expect(frame).toContain("content");
    expect(frame).not.toContain("<script>");
    expect(frame).not.toContain("</script>");
  });

  it("handles unclosed code fences while streaming", () => {
    const markdown = "```python\nprint('partial')";
    const { lastFrame } = renderApp(
      <MarkdownRenderer content={markdown} isStreaming />,
    );
    const frame = lastFrame() ?? "";
    expect(frame).toContain("[PYTHON]");
    expect(frame).toContain("print");
    expect(frame).toContain("streaming code block");
  });

  it("handles partial inline markdown without crashing", () => {
    const { lastFrame } = renderApp(
      <MarkdownRenderer content="this is **incom" isStreaming />,
    );
    const frame = lastFrame() ?? "";
    expect(frame).toContain("this is");
    expect(frame).toContain("incom");
  });
});

describe("cached parser", () => {
  it("reuses cached Marked parser across calls", () => {
    const result1 = renderMarkdown("**bold**", false);
    const result2 = renderMarkdown("*italic*", false);
    // Both should succeed (parser not corrupted by reuse)
    expect(result1).toContain("bold");
    expect(result2).toContain("italic");
  });
});

describe("markdown helpers", () => {
  it("stripHtml removes tags", () => {
    expect(stripHtml("a <b>bold</b> c")).toBe("a bold c");
  });

  it("withClosedCodeFence appends closing fence for odd count during streaming", () => {
    const result = withClosedCodeFence("```ts\nconst x = 1", true);
    expect(result.hasPendingCodeFence).toBe(true);
    expect(result.markdown.endsWith("```"));
  });

  it("renderMarkdown returns string output", () => {
    const output = renderMarkdown("**ok**", false);
    expect(typeof output).toBe("string");
    expect(output).toContain("ok");
  });
});

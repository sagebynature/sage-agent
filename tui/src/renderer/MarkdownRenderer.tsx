import { Text } from "ink";
import { Marked, type RendererObject } from "marked";
import { markedTerminal } from "marked-terminal";
import chalk from "chalk";
import type { ReactNode } from "react";
import { formatCodeBlock } from "./CodeBlock.js";

const HTML_TAG_PATTERN = /<[^>]*>/g;
const CODE_FENCE_PATTERN = /```/g;

export interface MarkdownRendererProps {
  content: string;
  isStreaming?: boolean;
}

function stripHtml(input: string): string {
  return input.replace(HTML_TAG_PATTERN, "");
}

function withClosedCodeFence(input: string, isStreaming: boolean): {
  markdown: string;
  hasPendingCodeFence: boolean;
} {
  const fenceCount = (input.match(CODE_FENCE_PATTERN) ?? []).length;
  const hasPendingCodeFence = isStreaming && fenceCount % 2 === 1;

  if (!hasPendingCodeFence) {
    return { markdown: input, hasPendingCodeFence: false };
  }

  return {
    markdown: `${input}\n\n\`\`\``,
    hasPendingCodeFence: true,
  };
}

function createMarkedRenderer(): Marked {
  const parser = new Marked();
  const terminalExtension = markedTerminal({
    reflowText: false,
    showSectionPrefix: true,
    tab: 2,
    emoji: true,
  });

  const rendererOverride: RendererObject = {
    code(token) {
      return `${formatCodeBlock(token.text, token.lang)}\n\n`;
    },
    html() {
      return "";
    },
  };

  parser.use(terminalExtension, { renderer: rendererOverride });
  return parser;
}

function renderMarkdown(content: string, isStreaming: boolean): string {
  const strippedContent = stripHtml(content);
  const { markdown, hasPendingCodeFence } = withClosedCodeFence(strippedContent, isStreaming);
  const parser = createMarkedRenderer();

  try {
    const rendered = parser.parse(markdown, {
      async: false,
      gfm: true,
      breaks: true,
    });

    const output = typeof rendered === "string" ? rendered : strippedContent;
    if (hasPendingCodeFence) {
      return `${output}\n${chalk.dim("... streaming code block")}`;
    }

    return output;
  } catch {
    const fallback = isStreaming ? chalk.dim(strippedContent) : strippedContent;
    return fallback;
  }
}

export function MarkdownRenderer({ content, isStreaming = false }: MarkdownRendererProps): ReactNode {
  const rendered = renderMarkdown(content, isStreaming);
  return <Text>{rendered}</Text>;
}

export { stripHtml, withClosedCodeFence, renderMarkdown };

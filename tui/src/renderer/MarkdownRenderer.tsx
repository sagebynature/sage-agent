import { Text } from "ink";
import { Marked, type RendererObject, type Token, type Tokens } from "marked";
import { markedTerminal } from "marked-terminal";
import chalk from "chalk";
import type { ReactNode } from "react";
import { formatCodeBlock } from "./CodeBlock.js";

const HTML_TAG_PATTERN = /<[^>]*>/g;
const CODE_FENCE_PATTERN = /```/g;
const ANSI_PATTERN = /\u001B\[[0-9;]*m/g;
const LIST_INDENT = "  ";

interface TokenParser {
  parse(tokens: Token[], top?: boolean): string;
  parseInline(tokens: Token[]): string;
}

export interface MarkdownRendererProps {
  content: string;
  isStreaming?: boolean;
}

function stripHtml(input: string): string {
  return input.replace(HTML_TAG_PATTERN, "");
}

function visibleLength(input: string): number {
  return input.replace(ANSI_PATTERN, "").length;
}

function prefixLines(input: string, prefix: string): string {
  return input
    .split("\n")
    .map((line) => (line.length > 0 ? `${prefix}${line}` : prefix.trimEnd()))
    .join("\n");
}

function renderList(
  parser: TokenParser,
  token: Tokens.List,
  depth = 0,
): string {
  const startIndex = typeof token.start === "number" ? token.start : 1;

  const rendered = token.items
    .map((item, index) => renderListItem(parser, item, depth, token.ordered ? startIndex + index : null))
    .join("\n");

  return `${rendered}\n\n`;
}

function renderListItem(
  parser: TokenParser,
  item: Tokens.ListItem,
  depth: number,
  orderedIndex: number | null,
): string {
  const indent = LIST_INDENT.repeat(depth);
  const marker = item.task
    ? item.checked
      ? chalk.green("☑")
      : chalk.yellow("☐")
    : orderedIndex !== null
      ? chalk.cyan(`${orderedIndex}.`)
      : chalk.cyan(depth === 0 ? "•" : "◦");

  const contentTokens = item.tokens.filter((token) => token.type !== "list");
  const nestedLists = item.tokens.filter((token): token is Tokens.List => token.type === "list");
  const inlineContent = contentTokens.length > 0 ? parser.parse(contentTokens, false).trimEnd() : "";
  const continuationIndent = `${indent}${" ".repeat(visibleLength(marker) + 1)}`;
  const lines: string[] = [];

  if (inlineContent.length > 0) {
    const [firstLine, ...rest] = inlineContent.split("\n");
    lines.push(`${indent}${marker} ${firstLine}`);

    for (const line of rest) {
      lines.push(`${continuationIndent}${line}`);
    }
  } else {
    lines.push(`${indent}${marker}`);
  }

  for (const nestedList of nestedLists) {
    lines.push(renderList(parser, nestedList, depth + 1).trimEnd());
  }

  return lines.join("\n");
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

let cachedParser: Marked | null = null;

function getMarkedRenderer(): Marked {
  if (cachedParser) return cachedParser;

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
    heading({ tokens, depth }) {
      const text = this.parser.parseInline(tokens).trim();

      if (depth === 1) {
        return `${chalk.bold.cyan(text)}\n${chalk.dim("═".repeat(Math.max(visibleLength(text), 8)))}\n\n`;
      }

      if (depth === 2) {
        return `${chalk.bold.blue(text)}\n${chalk.dim("─".repeat(Math.max(visibleLength(text), 6)))}\n\n`;
      }

      return `${chalk.cyan("▸")} ${chalk.bold(text)}\n\n`;
    },
    hr() {
      return `${chalk.dim("─".repeat(48))}\n\n`;
    },
    blockquote({ tokens }) {
      const content = this.parser.parse(tokens).trim();
      const quoted = prefixLines(content, `${chalk.yellow("│")} `);
      return `${chalk.dim("quote")}\n${quoted}\n\n`;
    },
    list(token) {
      return renderList(this.parser as TokenParser, token);
    },
    paragraph({ tokens }) {
      return `${this.parser.parseInline(tokens)}\n\n`;
    },
    strong({ tokens }) {
      return chalk.bold(this.parser.parseInline(tokens));
    },
    em({ tokens }) {
      return chalk.italic(this.parser.parseInline(tokens));
    },
    codespan({ text }) {
      return chalk.black.bgYellow(` ${text} `);
    },
    del({ tokens }) {
      return chalk.strikethrough(this.parser.parseInline(tokens));
    },
    link({ href, tokens }) {
      const text = this.parser.parseInline(tokens).trim() || href;

      if (text === href) {
        return chalk.underline.blue(href);
      }

      return `${chalk.underline.blue(text)} ${chalk.dim(`<${href}>`)}`;
    },
    image({ href, text }) {
      const label = text?.trim() || "image";
      return `${chalk.magenta("[image]")} ${label} ${chalk.dim(`<${href}>`)}`;
    },
    html() {
      return "";
    },
  };

  parser.use(terminalExtension);
  parser.use({ renderer: rendererOverride });
  cachedParser = parser;
  return parser;
}

function renderMarkdown(content: string, isStreaming: boolean): string {
  const strippedContent = stripHtml(content);
  const { markdown, hasPendingCodeFence } = withClosedCodeFence(strippedContent, isStreaming);
  const parser = getMarkedRenderer();

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

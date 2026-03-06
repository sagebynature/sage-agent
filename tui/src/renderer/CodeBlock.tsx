import { Text } from "ink";
import chalk from "chalk";
import { highlight, supportsLanguage } from "cli-highlight";
import type { ReactNode } from "react";

const LANGUAGE_ALIASES: Record<string, string> = {
  ts: "typescript",
  typescript: "typescript",
  js: "javascript",
  javascript: "javascript",
  py: "python",
  python: "python",
  json: "json",
  yml: "yaml",
  yaml: "yaml",
  sh: "bash",
  shell: "bash",
  bash: "bash",
  golang: "go",
  go: "go",
  rs: "rust",
  rust: "rust",
  html: "html",
  css: "css",
};

const SUPPORTED_LANGUAGES = new Set([
  "typescript",
  "javascript",
  "python",
  "json",
  "yaml",
  "bash",
  "go",
  "rust",
  "html",
  "css",
]);

export interface CodeBlockProps {
  code: string;
  language?: string | null;
  dimmed?: boolean;
}

function normalizeLanguage(language?: string | null): string | undefined {
  const normalized = language?.trim().toLowerCase();
  if (!normalized) {
    return undefined;
  }

  const alias = LANGUAGE_ALIASES[normalized] ?? normalized;
  if (!SUPPORTED_LANGUAGES.has(alias)) {
    return undefined;
  }

  if (!supportsLanguage(alias)) {
    return undefined;
  }

  return alias;
}

function formatLanguageLabel(language?: string): string {
  const label = language ? language.toUpperCase() : "TEXT";
  return chalk.bold.cyan(`[${label}]`);
}

export function formatCodeBlock(code: string, language?: string | null, dimmed = false): string {
  const normalizedLanguage = normalizeLanguage(language);
  const highlighted = normalizedLanguage
    ? highlight(code, { language: normalizedLanguage, ignoreIllegals: true })
    : chalk.yellow(code);

  const label = formatLanguageLabel(normalizedLanguage);
  const lines = highlighted.split("\n").map((line) => `${chalk.dim("│")} ${line}`);
  const block = `${label}\n${lines.join("\n")}`;

  if (dimmed) {
    return chalk.dim(block);
  }

  return block;
}

export function CodeBlock({ code, language, dimmed = false }: CodeBlockProps): ReactNode {
  return <Text>{formatCodeBlock(code, language, dimmed)}</Text>;
}

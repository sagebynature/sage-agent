import { detectCapabilities } from "./terminal.js";

export interface IconSet {
  check: string;
  pending: string;
  running: string;
  failed: string;
  spinner: string;
  bolt: string;
  search: string;
  folder: string;
  success: string;
  error: string;
  arrow: string;
  bullet: string;
}

const UNICODE_ICONS: IconSet = {
  check: "✓",
  pending: "○",
  running: "▶",
  failed: "✗",
  spinner: "⟳",
  bolt: "⚡",
  search: "🔍",
  folder: "📁",
  success: "✅",
  error: "❌",
  arrow: "→",
  bullet: "•",
};

const ASCII_ICONS: IconSet = {
  check: "[x]",
  pending: "[ ]",
  running: ">",
  failed: "[!]",
  spinner: "*",
  bolt: "!",
  search: "?",
  folder: "/",
  success: "[OK]",
  error: "[ERR]",
  arrow: "->",
  bullet: "*",
};

let cachedIcons: IconSet | null = null;

export function getIcons(forceUnicode?: boolean): IconSet {
  if (forceUnicode !== undefined) {
    return forceUnicode ? UNICODE_ICONS : ASCII_ICONS;
  }
  if (!cachedIcons) {
    const caps = detectCapabilities();
    cachedIcons = caps.unicode ? UNICODE_ICONS : ASCII_ICONS;
  }
  return cachedIcons;
}

/** @internal Exposed for tests that need to verify cache behaviour. */
export function resetIconCache(): void {
  cachedIcons = null;
}

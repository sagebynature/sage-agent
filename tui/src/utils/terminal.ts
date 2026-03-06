export interface TerminalCapabilities {
  colorDepth: 24 | 256 | 16 | 0;
  unicode: boolean;
  width: number;
  height: number;
  isInteractive: boolean;
}

export function detectCapabilities(): TerminalCapabilities {
  const colorterm = process.env["COLORTERM"];
  const term = process.env["TERM"] ?? "";
  const noColor = process.env["NO_COLOR"];

  let colorDepth: 24 | 256 | 16 | 0;
  if (colorterm === "truecolor" || colorterm === "24bit") {
    colorDepth = 24;
  } else if (term.includes("256color")) {
    colorDepth = 256;
  } else if (term === "dumb" || noColor === "1" || noColor === "") {
    colorDepth = 0;
  } else {
    colorDepth = 16;
  }

  const lang = process.env["LANG"] ?? "";
  const lcAll = process.env["LC_ALL"] ?? "";
  const wtSession = process.env["WT_SESSION"];
  let unicode: boolean;
  if (term === "dumb") {
    unicode = false;
  } else if (
    lang.toUpperCase().includes("UTF-8") ||
    lang.toUpperCase().includes("UTF8") ||
    lcAll.toUpperCase().includes("UTF-8") ||
    lcAll.toUpperCase().includes("UTF8") ||
    wtSession !== undefined
  ) {
    unicode = true;
  } else {
    // Most modern terminals support Unicode even without UTF-8 locale vars
    unicode = true;
  }

  const width = process.stdout.columns ?? 80;
  const height = process.stdout.rows ?? 24;

  const isInteractive = process.stdout.isTTY === true;

  return { colorDepth, unicode, width, height, isInteractive };
}

export const MIN_WIDTH = 80;
export const MIN_HEIGHT = 24;

export function isBelowMinimum(caps: TerminalCapabilities): boolean {
  return caps.width < MIN_WIDTH || caps.height < MIN_HEIGHT;
}

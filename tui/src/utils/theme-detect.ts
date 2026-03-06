type Theme = "dark" | "light";

const TERM_PROGRAM_THEME_MAP: Record<string, Theme> = {
  "iTerm.app": "dark",
  WarpTerminal: "dark",
  WezTerm: "dark",
  vscode: "dark",
  Hyper: "dark",
  Apple_Terminal: "light",
};

function readThemeOverride(value: string | undefined): Theme | null {
  const normalized = value?.trim().toLowerCase();
  if (normalized === "dark") {
    return "dark";
  }
  if (normalized === "light") {
    return "light";
  }
  return null;
}

function detectFromColorFgBg(value: string | undefined): Theme | null {
  if (!value) {
    return null;
  }

  const segments = value.split(";");
  const backgroundRaw = segments[segments.length - 1];
  if (!backgroundRaw) {
    return null;
  }

  const background = Number.parseInt(backgroundRaw, 10);
  if (Number.isNaN(background)) {
    return null;
  }

  return background > 7 ? "dark" : "light";
}

function detectFromTermProgram(value: string | undefined): Theme | null {
  if (!value) {
    return null;
  }

  return TERM_PROGRAM_THEME_MAP[value] ?? null;
}

export function detectTheme(): Theme {
  const overridden = readThemeOverride(process.env.SAGE_THEME);
  if (overridden) {
    return overridden;
  }

  const fromColorFgBg = detectFromColorFgBg(process.env.COLORFGBG);
  if (fromColorFgBg) {
    return fromColorFgBg;
  }

  const fromTermProgram = detectFromTermProgram(process.env.TERM_PROGRAM);
  if (fromTermProgram) {
    return fromTermProgram;
  }

  return "dark";
}

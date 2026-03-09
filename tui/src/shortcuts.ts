export interface InputKey {
  ctrl?: boolean;
  pageUp?: boolean;
  pageDown?: boolean;
  upArrow?: boolean;
  downArrow?: boolean;
  escape?: boolean;
}

export const SHORTCUT_LABELS = {
  leader: "Ctrl+Space",
  clear: "Ctrl+Space, L",
  reset: "Ctrl+Space, N",
  approvePermission: "Ctrl+Space, P",
  saveSession: "Ctrl+Space, S",
  toggleVerbosity: "Ctrl+Space, V",
  toggleEventPane: "Ctrl+Space, E",
  quit: "Ctrl+C",
  newline: "Ctrl+J",
  previousEvent: "Ctrl+Space, Up",
  nextEvent: "Ctrl+Space, Down",
} as const;

export function isLeaderShortcut(input: string, key: InputKey): boolean {
  return input === "\0" || Boolean(key.ctrl && (input === " " || input === "`"));
}

export type LeaderAction =
  | "clear"
  | "reset"
  | "approvePermission"
  | "saveSession"
  | "toggleVerbosity"
  | "toggleEventPane"
  | "previousEvent"
  | "nextEvent"
  | "cancel"
  | null;

export function resolveLeaderAction(input: string, key: InputKey): LeaderAction {
  if (key.escape || isLeaderShortcut(input, key)) {
    return "cancel";
  }

  if (key.upArrow) {
    return "previousEvent";
  }

  if (key.downArrow) {
    return "nextEvent";
  }

  switch (input.toLowerCase()) {
    case "l":
      return "clear";
    case "n":
      return "reset";
    case "p":
      return "approvePermission";
    case "s":
      return "saveSession";
    case "v":
      return "toggleVerbosity";
    case "e":
      return "toggleEventPane";
    default:
      return null;
  }
}

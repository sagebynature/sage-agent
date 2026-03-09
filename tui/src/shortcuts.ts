export interface InputKey {
  ctrl?: boolean;
  pageUp?: boolean;
  pageDown?: boolean;
  upArrow?: boolean;
  downArrow?: boolean;
  escape?: boolean;
}

export const SHORTCUT_LABELS = {
  leader: "Ctrl+G",
  clear: "Ctrl+G, L",
  reset: "Ctrl+G, N",
  approvePermission: "Ctrl+G, P",
  saveSession: "Ctrl+G, S",
  toggleVerbosity: "Ctrl+G, V",
  toggleEventPane: "Ctrl+G, E",
  quit: "Ctrl+C",
  newline: "Ctrl+J",
  previousEvent: "Ctrl+G, Up",
  nextEvent: "Ctrl+G, Down",
} as const;

export function isLeaderShortcut(input: string, key: InputKey): boolean {
  return Boolean(key.ctrl && input === "g");
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

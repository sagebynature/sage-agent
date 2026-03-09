export interface InputKey {
  ctrl?: boolean;
  meta?: boolean;
  pageUp?: boolean;
  pageDown?: boolean;
  upArrow?: boolean;
  downArrow?: boolean;
}

export const SHORTCUT_LABELS = {
  clear: "Alt+L",
  reset: "Alt+N",
  approvePermission: "Alt+P",
  saveSession: "Alt+S",
  toggleVerbosity: "Alt+V",
  toggleEventPane: "Alt+E",
  quit: "Ctrl+C",
  newline: "Ctrl+J",
  previousEvent: "Alt+Up",
  nextEvent: "Alt+Down",
} as const;

function isMetaLetter(input: string, key: InputKey, letter: string): boolean {
  return Boolean(key.meta && input.toLowerCase() === letter);
}

function isCtrlLetter(input: string, key: InputKey, letter: string): boolean {
  return Boolean(key.ctrl && input === letter);
}

export function isClearShortcut(input: string, key: InputKey): boolean {
  return isMetaLetter(input, key, "l") || isCtrlLetter(input, key, "l");
}

export function isResetShortcut(input: string, key: InputKey): boolean {
  return isMetaLetter(input, key, "n") || isCtrlLetter(input, key, "n");
}

export function isApprovePermissionShortcut(input: string, key: InputKey): boolean {
  return isMetaLetter(input, key, "p") || isCtrlLetter(input, key, "p");
}

export function isSaveShortcut(input: string, key: InputKey): boolean {
  return isMetaLetter(input, key, "s") || isCtrlLetter(input, key, "s");
}

export function isToggleVerbosityShortcut(input: string, key: InputKey): boolean {
  return isMetaLetter(input, key, "v") || isCtrlLetter(input, key, "v");
}

export function isToggleEventPaneShortcut(input: string, key: InputKey): boolean {
  return isMetaLetter(input, key, "e") || isCtrlLetter(input, key, "e");
}

export function isPreviousEventShortcut(key: InputKey): boolean {
  return Boolean((key.meta && key.upArrow) || (key.ctrl && key.pageUp));
}

export function isNextEventShortcut(key: InputKey): boolean {
  return Boolean((key.meta && key.downArrow) || (key.ctrl && key.pageDown));
}

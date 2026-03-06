export type ShortcutMode = "normal" | "insert" | "command" | "leader";
export type ShortcutCategory = "navigation" | "session" | "view" | "input" | "agent" | "leader";

export interface KeyBinding {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  meta?: boolean;
  modes: ShortcutMode[];
  action: string;
  description: string;
  category: ShortcutCategory;
}

export interface LeaderState {
  active: boolean;
  startedAt: number | null;
  timeout: number;
}

export type ShortcutAction = string;

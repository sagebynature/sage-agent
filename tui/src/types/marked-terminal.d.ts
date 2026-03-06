declare module "marked-terminal" {
  import type { MarkedExtension } from "marked";

  export interface MarkedTerminalOptions {
    reflowText?: boolean;
    showSectionPrefix?: boolean;
    tab?: number | string;
    emoji?: boolean;
  }

  export function markedTerminal(options?: MarkedTerminalOptions, highlightOptions?: Record<string, unknown>): MarkedExtension;
}

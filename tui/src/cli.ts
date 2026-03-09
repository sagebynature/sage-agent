import type { SageClientOptions } from "./ipc/types.js";

export function buildClientOptions(argv: string[]): SageClientOptions | undefined {
  const enableYolo = argv.includes("--yolo") || argv.includes("-y");
  if (!enableYolo) {
    return undefined;
  }

  return {
    args: ["serve", "--yolo"],
  };
}

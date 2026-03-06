export const COLORS = {
  idle: "green",
  streaming: "yellow",
  tool: "blue",
  error: "red",
  permission: "magenta",

  accent: "cyan",
  dimmed: "gray",
  brand: "magenta",

  headerIdle: "#2d6a4f",
  headerStreaming: "#e9c46a",
  headerTool: "#457b9d",
  headerError: "#e63946",
  headerPermission: "#7b2d8b",
} as const;

export type SemanticColor = keyof typeof COLORS;

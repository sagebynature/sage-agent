export interface ToolSummary {
  name: string;
  callId: string;
  arguments: Record<string, unknown>;
  result?: string;
  error?: string;
  durationMs?: number;
  status: "running" | "completed" | "failed";
  startedAt?: number;
}

export interface ComplexitySummary {
  score: number;
  level: "simple" | "medium" | "complex";
  version?: string;
}

export interface OutputBlock {
  id: string;
  type: "user" | "text" | "tool" | "error" | "system";
  content: string;
  tools?: ToolSummary[];
  timestamp: number;
}

export interface ActiveStream {
  runId: string;
  content: string;
  tools: ToolSummary[];
  isThinking: boolean;
  startedAt: number;
  complexity?: ComplexitySummary;
}

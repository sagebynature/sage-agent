import { Box, Text } from "ink";
import { memo, type ReactNode } from "react";
import type { EventRecord } from "../types/events.js";

interface ComplexityPanelProps {
  event: EventRecord | null;
  maxHeight?: number;
}

interface ComplexityFactorView {
  kind: string;
  contribution: number;
  value?: string;
}

function complexityRecord(event: EventRecord | null): Record<string, unknown> | null {
  if (!event) {
    return null;
  }
  const complexity = event.payload.complexity;
  return typeof complexity === "object" && complexity !== null && !Array.isArray(complexity)
    ? (complexity as Record<string, unknown>)
    : null;
}

function toFactorViews(value: unknown): ComplexityFactorView[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => {
    if (typeof item !== "object" || item === null || Array.isArray(item)) {
      return [];
    }
    const record = item as Record<string, unknown>;
    const kind = typeof record.kind === "string" ? record.kind : null;
    const contribution =
      typeof record.contribution === "number" ? record.contribution : null;
    if (!kind || contribution === null) {
      return [];
    }
    const factor: ComplexityFactorView = { kind, contribution };
    const rawValue = record.value;
    if (
      typeof rawValue === "string"
      || typeof rawValue === "number"
      || typeof rawValue === "boolean"
    ) {
      factor.value = String(rawValue);
    }
    return [factor];
  });
}

function displayName(kind: string): string {
  switch (kind) {
    case "message_length":
      return "message length";
    case "tool_count":
      return "tools";
    case "code_markers":
      return "code markers";
    case "conversation_depth":
      return "history depth";
    case "system_prompt_length":
      return "system prompt";
    default:
      return kind.replaceAll("_", " ");
  }
}

function metadataLine(complexity: Record<string, unknown>): string | null {
  const metadata = complexity.metadata;
  if (typeof metadata !== "object" || metadata === null || Array.isArray(metadata)) {
    return null;
  }
  const record = metadata as Record<string, unknown>;
  const parts: string[] = [];
  if (typeof record.message_chars === "number") {
    parts.push(`${record.message_chars} chars`);
  }
  if (typeof record.tool_count === "number") {
    parts.push(`${record.tool_count} tools`);
  }
  if (typeof record.message_count === "number") {
    parts.push(`${record.message_count} msgs`);
  }
  return parts.length > 0 ? parts.join(" | ") : null;
}

export const ComplexityPanel = memo(function ComplexityPanel({
  event,
  maxHeight,
}: ComplexityPanelProps): ReactNode {
  const complexity = complexityRecord(event);
  const factors = complexity ? toFactorViews(complexity.factors) : [];
  const score =
    complexity && typeof complexity.score === "number" ? complexity.score : null;
  const level =
    complexity && typeof complexity.level === "string" ? complexity.level : null;
  const version =
    complexity && typeof complexity.version === "string" ? complexity.version : null;
  const meta = complexity ? metadataLine(complexity) : null;

  return (
    <Box
      width={34}
      flexShrink={0}
      flexDirection="column"
      borderStyle="round"
      borderColor="gray"
      paddingX={1}
      {...(maxHeight ? { height: maxHeight, overflowY: "hidden" as const } : {})}
    >
      <Text bold>Complexity Score</Text>
      {!complexity || score === null || !level ? (
        <Text dimColor>No complexity data</Text>
      ) : (
        <>
          <Text>{`C${score} ${level}`}</Text>
          {version ? <Text dimColor>{version}</Text> : null}
          {meta ? <Text dimColor>{meta}</Text> : null}
          {factors.length > 0 ? (
            <Box flexDirection="column" marginTop={1}>
              {factors.map((factor) => (
                <Text key={factor.kind}>
                  {`${displayName(factor.kind)} +${factor.contribution}`}
                  {factor.value ? <Text dimColor>{` (${factor.value})`}</Text> : null}
                </Text>
              ))}
            </Box>
          ) : (
            <Text dimColor>No factor breakdown</Text>
          )}
        </>
      )}
    </Box>
  );
});

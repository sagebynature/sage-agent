import { Box, Text } from "ink";
import type { ReactNode } from "react";
import type { UsageState, PermissionState, AgentNode } from "../types/state.js";
import type { ActiveStream } from "../types/blocks.js";

type AppMode = "idle" | "connecting" | "streaming" | "tool" | "permission" | "error";

interface BottomBarProps {
  usage: UsageState;
  activeStream: ActiveStream | null;
  permissions: PermissionState[];
  error: string | null;
  connectionStatus: "connecting" | "connected" | "disconnected" | "error";
  agents: AgentNode[];
  sessionName?: string;
}

function contextBar(percent: number): string {
  const filled = Math.round(percent / 10);
  const empty = 10 - filled;
  return "█".repeat(filled) + "░".repeat(empty);
}

function contextColor(percent: number): string {
  if (percent >= 90) return "red";
  if (percent >= 70) return "yellow";
  return "green";
}

function getMode(props: BottomBarProps): AppMode {
  if (props.connectionStatus === "connecting" || props.connectionStatus === "disconnected") return "connecting";
  if (props.error) return "error";
  if (props.permissions.some((p) => p.status === "pending")) return "permission";
  if (props.activeStream) {
    const hasRunningTool = props.activeStream.tools.some((t) => t.status === "running");
    if (hasRunningTool) return "tool";
    return "streaming";
  }
  return "idle";
}

function ModeIndicator({ props }: { props: BottomBarProps }): ReactNode {
  const mode = getMode(props);

  switch (mode) {
    case "connecting":
      return <Text color="yellow">{"● connecting..."}</Text>;
    case "streaming":
      return (
        <Text>
          <Text color="yellow">{"● streaming"}</Text>
          <Text dimColor>{" — ESC to cancel"}</Text>
        </Text>
      );
    case "tool": {
      const running = props.activeStream?.tools.find((t) => t.status === "running");
      return (
        <Text>
          <Text color="blue">{"● "}{running?.name ?? "tool"}</Text>
          <Text dimColor>{" — ESC to cancel"}</Text>
        </Text>
      );
    }
    case "permission":
      return (
        <Text>
          <Text color="green">[y]</Text>{" Once "}
          <Text color="green">[a]</Text>{" Session "}
          <Text color="green">[s]</Text>{" Similar "}
          <Text color="red">[n]</Text>{" Deny "}
          <Text color="yellow">[e]</Text>{" Edit"}
        </Text>
      );
    case "error":
      return <Text color="red">{"● error — ESC to dismiss"}</Text>;
    case "idle":
      return <Text dimColor>{"/ commands | ctrl+c quit"}</Text>;
    default:
      return null;
  }
}

export function BottomBar(props: BottomBarProps): ReactNode {
  const { usage, agents, sessionName } = props;
  const cost = `$${usage.totalCost.toFixed(2)}`;
  const model = usage.model || "no model";
  const pct = usage.contextUsagePercent;
  const activeAgents = agents.filter((a) => a.status === "active").length;

  return (
    <Box>
      <Text dimColor>
        {"  "}{model}
        {" | "}
        <Text color={contextColor(pct)}>{contextBar(pct)}</Text>
        {" "}{pct}%
        {" | "}{cost}
      </Text>
      {activeAgents > 0 && <Text color="magenta">{" | "}{activeAgents} agent{activeAgents > 1 ? "s" : ""}</Text>}
      {sessionName && <Text dimColor>{" | "}{sessionName}</Text>}
      <Text dimColor>{"  "}</Text>
      <ModeIndicator props={props} />
    </Box>
  );
}

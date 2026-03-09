import { execFileSync } from "node:child_process";
import { homedir } from "node:os";
import { sep } from "node:path";
import { Box, Text } from "ink";
import { memo, type ReactNode } from "react";
import type { UsageState, PermissionState, AgentNode } from "../types/state.js";
import type { ActiveStream } from "../types/blocks.js";
import type { RunSummary, VerbosityMode, EventRecord } from "../types/events.js";
import { SHORTCUT_LABELS } from "../shortcuts.js";

type AppMode = "idle" | "connecting" | "streaming" | "tool" | "permission" | "error";

interface BottomBarProps {
  width: number;
  cwd?: string;
  gitBranch?: string;
  usage: UsageState;
  activeStream: ActiveStream | null;
  permissions: PermissionState[];
  error: string | null;
  connectionStatus: "connecting" | "connected" | "disconnected" | "error";
  agents: AgentNode[];
  sessionName?: string;
  modelName?: string;
  verbosity: VerbosityMode;
  showEventPane: boolean;
  leaderActive?: boolean;
  activeRun?: RunSummary;
  selectedEvent?: EventRecord | null;
}

function formatCurrentDirectory(cwd: string): string {
  const home = homedir();
  if (cwd === home) return "~";
  if (cwd.startsWith(`${home}${sep}`)) {
    return `~${cwd.slice(home.length)}`;
  }
  return cwd;
}

function resolveGitBranch(cwd: string): string | undefined {
  try {
    const branch = execFileSync("git", ["rev-parse", "--abbrev-ref", "HEAD"], {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();

    return branch && branch !== "HEAD" ? branch : undefined;
  } catch {
    return undefined;
  }
}

function contextColor(percent: number): string {
  if (percent >= 90) return "red";
  if (percent >= 70) return "yellow";
  return "green";
}

const DEFAULT_CWD = formatCurrentDirectory(process.cwd());
const DEFAULT_GIT_BRANCH = resolveGitBranch(process.cwd());

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
  if (props.leaderActive) {
    return (
      <Text color="cyan">
        {"● leader"}
        <Text dimColor>{" — [v]erbosity [e]vents [l]clear [n]reset [p]approve [s]save [↑/↓] event [esc] cancel"}</Text>
      </Text>
    );
  }

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
      return <Text dimColor>{`/ commands | ${SHORTCUT_LABELS.leader.toLowerCase()} shortcuts | ${SHORTCUT_LABELS.quit.toLowerCase()} quit`}</Text>;
    default:
      return null;
  }
}

export const BottomBar = memo(function BottomBar(props: BottomBarProps): ReactNode {
  const {
    width,
    cwd = DEFAULT_CWD,
    gitBranch = DEFAULT_GIT_BRANCH,
    usage,
    agents,
    sessionName,
    modelName,
    verbosity,
    showEventPane,
    leaderActive,
    activeRun,
    selectedEvent,
  } = props;
  const cost = `$${usage.totalCost.toFixed(2)}`;
  const agentLabel = sessionName || "no agent";
  const activeModel = modelName || usage.model || "no model";
  const pct = usage.contextUsagePercent;
  const activeAgents = agents.filter((a) => a.status === "active").length;
  const runLabel = activeRun?.runId ? activeRun.runId.slice(0, 8) : undefined;
  const agentPath = selectedEvent?.agentPath.join(" > ") || activeRun?.agentPath.join(" > ");

  return (
    <Box width={width} flexDirection="column">
      <Text wrap="truncate-end">
        <Text>{"  "}</Text>
        <Text>{cwd}</Text>
        {gitBranch && (
          <>
            <Text dimColor>{" | git "}</Text>
            <Text color="cyan">{gitBranch}</Text>
          </>
        )}
        <Text dimColor>{" | "}</Text>
        <Text>{agentLabel}</Text>
        <Text dimColor>{" | "}</Text>
        <Text>{activeModel}</Text>
      </Text>
      <Text wrap="truncate-end">
        <Text dimColor>{"  "}</Text>
        <ModeIndicator props={props} />
        <Text dimColor>{" | "}</Text>
        <Text color={contextColor(pct)}>{pct}% used</Text>
        <Text dimColor>{" | "}{cost}</Text>
        {activeAgents > 0 && <Text dimColor>{" | "}{activeAgents} active agent{activeAgents > 1 ? "s" : ""}</Text>}
        <Text dimColor>{" | "}{verbosity}{showEventPane ? "+events" : ""}{leaderActive ? " | leader" : ""}</Text>
        {runLabel && <Text dimColor>{" | run "}{runLabel}</Text>}
        {agentPath && <Text dimColor>{" | "}{agentPath}</Text>}
      </Text>
    </Box>
  );
});

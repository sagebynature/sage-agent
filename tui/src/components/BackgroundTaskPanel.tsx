import React, { useState } from "react";
import { Box, Text, useInput } from "ink";
import { COLORS } from "../theme/colors";
import { TaskStatus, TaskStatusBadge } from "./TaskStatusBadge";

export interface BackgroundTask {
  taskId: string;
  agentName: string;
  description: string;
  status: TaskStatus;
  startedAt?: number;
  completedAt?: number;
  result?: string;
  error?: string;
}

export interface BackgroundTaskPanelProps {
  tasks: BackgroundTask[];
  onCancel?: (taskId: string) => void;
  onRerun?: (taskId: string) => void;
}

export const BackgroundTaskPanel: React.FC<BackgroundTaskPanelProps> = ({
  tasks,
  onCancel,
  onRerun,
}) => {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());

  // Ensure selected index is within bounds
  if (tasks.length > 0 && selectedIndex >= tasks.length) {
    setSelectedIndex(tasks.length - 1);
  }

  useInput((input, key) => {
    if (tasks.length === 0) return;

    if (key.upArrow || input === "k") {
      setSelectedIndex((prev) => Math.max(0, prev - 1));
    }

    if (key.downArrow || input === "j") {
      setSelectedIndex((prev) => Math.min(tasks.length - 1, prev + 1));
    }

    if (key.return) {
      const task = tasks[selectedIndex];
      if (task) {
        setExpandedTasks((prev) => {
          const next = new Set(prev);
          if (next.has(task.taskId)) {
            next.delete(task.taskId);
          } else {
            next.add(task.taskId);
          }
          return next;
        });
      }
    }

    if (input === "c" && onCancel) {
      const task = tasks[selectedIndex];
      if (task && task.status === "running") {
        onCancel(task.taskId);
      }
    }

    if (input === "r" && onRerun) {
      const task = tasks[selectedIndex];
      if (task && task.status === "completed") {
        onRerun(task.taskId);
      }
    }
  });

  if (tasks.length === 0) {
    return (
      <Box borderStyle="round" borderColor={COLORS.dimmed} padding={1}>
        <Text color={COLORS.dimmed}>No background tasks</Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column" borderStyle="round" borderColor={COLORS.dimmed} padding={1}>
      {tasks.map((task, index) => {
        const isSelected = index === selectedIndex;
        // Expanded if manually expanded OR if failed (and thus error should be visible)
        // Actually, let's keep it simple: failed state auto-expands logic is visual.
        // If I want it strictly "expanded by default", I'd need to manage that in state initialization or effect,
        // but since tasks prop changes, effect is tricky.
        // Instead, I'll just treat "failed" as a condition to show details,
        // OR allow the user to toggle it.
        // If I interpret "Failed tasks: Error expanded by default" strictly, it means they start open.
        // But if the user toggles it closed, it should stay closed?
        // Let's assume "showDetails" logic: expanded OR (failed AND error exists).
        // But this prevents collapsing failed tasks if I hardcode the OR.
        // Let's stick to the visual representation: if failed, we show the error.

        const isExpanded = expandedTasks.has(task.taskId);
        const showDetails = isExpanded || (task.status === 'failed' && !!task.error);

        return (
          <Box key={task.taskId} flexDirection="column" marginBottom={1}>
            <Box>
              <Text color={isSelected ? COLORS.accent : undefined}>
                {isSelected ? "> " : "  "}
              </Text>
              <Text>{task.taskId.substring(0, 8)} </Text>
              <Box marginLeft={1} marginRight={1}>
                <Text color={COLORS.tool}>{task.agentName}</Text>
              </Box>
              <TaskStatusBadge status={task.status} />
              <Box marginLeft={1}>
                <Text>{formatDuration(task)}</Text>
              </Box>
            </Box>

            <Box marginLeft={2}>
              <Text dimColor>
                {task.description.length > 60 && !isExpanded
                  ? task.description.substring(0, 60) + "..."
                  : task.description}
              </Text>
            </Box>

            {showDetails && (
              <Box marginLeft={2} flexDirection="column" marginTop={0}>
                {isExpanded && task.description.length > 60 && (
                     <Text>Full Description: {task.description}</Text>
                )}

                {task.result && (
                  <Box flexDirection="column">
                    <Text underline>Result:</Text>
                    <Text>{task.result}</Text>
                  </Box>
                )}

                {task.error && (
                  <Box flexDirection="column">
                    <Text color={COLORS.error} underline>
                      Error:
                    </Text>
                    <Text color={COLORS.error}>{task.error}</Text>
                  </Box>
                )}
              </Box>
            )}
          </Box>
        );
      })}
    </Box>
  );
};

function formatDuration(task: BackgroundTask): string {
  if (!task.startedAt) return "";
  const end = task.completedAt || Date.now();
  const durationMs = end - task.startedAt;
  const seconds = Math.floor(durationMs / 1000);

  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}

export function useBackgroundTaskCount(tasks: BackgroundTask[]) {
  return {
    total: tasks.length,
    running: tasks.filter((t) => t.status === "running").length,
    completed: tasks.filter((t) => t.status === "completed").length,
    failed: tasks.filter((t) => t.status === "failed").length,
  };
}

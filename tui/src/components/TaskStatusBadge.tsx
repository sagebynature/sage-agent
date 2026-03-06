import React from "react";
import { Text } from "ink";
import Spinner from "ink-spinner";
import { COLORS } from "../theme/colors";

export type TaskStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

interface TaskStatusBadgeProps {
  status: TaskStatus;
}

export const TaskStatusBadge: React.FC<TaskStatusBadgeProps> = ({ status }) => {
  switch (status) {
    case "pending":
      return <Text color={COLORS.dimmed}>[pending]</Text>;
    case "running":
      return (
        <Text color={COLORS.tool}>
          [running <Spinner />]
        </Text>
      );
    case "completed":
      return <Text color={COLORS.idle}>[completed ✓]</Text>;
    case "failed":
      return <Text color={COLORS.error}>[failed ✗]</Text>;
    case "cancelled":
      return <Text color={COLORS.dimmed}>[cancelled ⊘]</Text>;
  }
};

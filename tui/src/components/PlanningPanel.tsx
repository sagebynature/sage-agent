import { Box, Text } from "ink";
import { usePlan } from "../contexts/PlanContext.js";
import { PlanTaskItem } from "./PlanTaskItem.js";
import { NotepadView } from "./NotepadView.js";

export function PlanningPanel() {
  const { state } = usePlan();
  const { name, tasks, notepadContent, createdAt } = state;

  if (!name) {
    return (
      <Box borderStyle="round" borderColor="dim" padding={1} flexDirection="column" alignItems="center">
        <Text color="dim">No active plan</Text>
      </Box>
    );
  }

  const completedTasks = tasks.filter((t) => t.status === "completed").length;
  const totalTasks = tasks.length;
  const progressPercent = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

  const width = 20;
  const completedWidth = Math.round((progressPercent / 100) * width);
  const remainingWidth = width - completedWidth;
  const progressBar = "█".repeat(completedWidth) + "░".repeat(remainingWidth);

  const runningTaskIndex = tasks.findIndex((t) => t.status === "running");

  return (
    <Box flexDirection="column" flexGrow={1} borderStyle="round" borderColor="blue" paddingX={1}>
      <Box flexDirection="column" marginBottom={1}>
        <Box justifyContent="space-between">
          <Text bold color="blue">{name}</Text>
          {createdAt && <Text dimColor>{createdAt}</Text>}
        </Box>
        <Box marginTop={1}>
          <Text>
            {completedTasks}/{totalTasks} tasks completed ({progressPercent}%)
          </Text>
          <Box marginLeft={1}>
            <Text color="green">{progressBar}</Text>
          </Box>
        </Box>
      </Box>

      <Box flexDirection="column" flexGrow={1} marginBottom={1}>
        <Text bold underline>Tasks</Text>
        <Box flexDirection="column" marginTop={0}>
          {tasks.map((task, index) => (
            <PlanTaskItem
              key={index}
              task={task}
              index={index}
              isActive={index === runningTaskIndex}
            />
          ))}
        </Box>
      </Box>

      <Box flexDirection="column" height="30%" borderStyle="single" borderColor="dim">
        <Text bold underline>Notepad</Text>
        <NotepadView content={notepadContent} />
      </Box>
    </Box>
  );
}

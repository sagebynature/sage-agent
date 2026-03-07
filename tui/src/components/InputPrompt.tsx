import { Box, Text } from "ink";
import TextInput from "ink-text-input";
import { type ReactNode, useState, useCallback } from "react";

interface InputPromptProps {
  onSubmit: (text: string) => void;
  isActive?: boolean;
}

function Divider(): ReactNode {
  return (
    <Box>
      <Text dimColor>{"─".repeat(80)}</Text>
    </Box>
  );
}

export function InputPrompt({ onSubmit, isActive = true }: InputPromptProps): ReactNode {
  const [value, setValue] = useState("");

  const handleSubmit = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      onSubmit(text);
      setValue("");
    },
    [onSubmit],
  );

  return (
    <Box flexDirection="column">
      <Divider />
      <Box>
        <Text color="cyan">{"> "}</Text>
        <TextInput
          value={value}
          onChange={setValue}
          onSubmit={handleSubmit}
          placeholder="Type your message..."
          focus={isActive}
        />
      </Box>
      <Divider />
    </Box>
  );
}

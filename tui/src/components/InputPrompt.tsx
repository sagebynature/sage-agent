import { Box, Text, useInput } from "ink";
import TextInput from "ink-text-input";
import {
  type ReactNode,
  useState,
  useCallback,
  useImperativeHandle,
  forwardRef,
  type Ref,
} from "react";
import { useInputHistory } from "../hooks/useInputHistory.js";
import { SlashCommands } from "./SlashCommands.js";

type InputMode = "normal" | "command";

export interface InputPromptHandle {
  clear: () => void;
  hasValue: () => boolean;
}

interface InputPromptProps {
  onSubmit: (text: string) => void;
  onCommand?: (command: string, args: string) => void;
  isActive?: boolean;
  width?: number;
}

function Divider({ width }: { width: number }): ReactNode {
  return (
    <Box>
      <Text dimColor>{"─".repeat(width)}</Text>
    </Box>
  );
}

export const InputPrompt = forwardRef(function InputPrompt(
  { onSubmit, onCommand, isActive = true, width = 80 }: InputPromptProps,
  ref: Ref<InputPromptHandle>,
): ReactNode {
  const [value, setValue] = useState("");
  const [mode, setMode] = useState<InputMode>("normal");
  const history = useInputHistory();

  useImperativeHandle(ref, () => ({
    clear: () => {
      setValue("");
      setMode("normal");
    },
    hasValue: () => value !== "",
  }));

  const handleSubmit = useCallback(
    (text: string) => {
      if (!text.trim()) return;

      history.addEntry(text);

      if (text.startsWith("/") && onCommand) {
        const spaceIndex = text.indexOf(" ");
        const commandName = spaceIndex === -1 ? text : text.slice(0, spaceIndex);
        const args = spaceIndex === -1 ? "" : text.slice(spaceIndex + 1);
        onCommand(commandName, args);
        setValue("");
        setMode("normal");
        return;
      }

      onSubmit(text);
      setValue("");
      setMode("normal");
    },
    [onSubmit, onCommand, history],
  );

  const handleSlashSelect = useCallback(
    (command: string, args: string) => {
      if (onCommand) {
        onCommand(`/${command}`, args);
      }
      setValue("");
      setMode("normal");
    },
    [onCommand],
  );

  const handleSlashDismiss = useCallback(() => {
    setMode("normal");
  }, []);

  const handleChange = useCallback((newValue: string) => {
    setValue(newValue);

    if (newValue.length === 1 && newValue === "/") {
      setMode("command");
      return;
    }

    if (newValue === "") {
      setMode("normal");
    }
  }, []);

  useInput((_, key) => {
    if (!isActive) return;

    if (key.upArrow && mode === "normal") {
      const entry = history.navigateUp();
      if (entry !== undefined) {
        setValue(entry);
      }
      return;
    }

    if (key.downArrow && mode === "normal") {
      const entry = history.navigateDown();
      setValue(entry ?? "");
      return;
    }

    if (key.escape) {
      if (mode !== "normal") {
        setMode("normal");
      }
      return;
    }
  });

  return (
    <Box flexDirection="column">
      <SlashCommands
        input={value}
        isActive={mode === "command"}
        onSelect={handleSlashSelect}
        onDismiss={handleSlashDismiss}
      />
      <Divider width={width} />
      <Box>
        <Text color="cyan">{"> "}</Text>
        <TextInput
          value={value}
          onChange={handleChange}
          onSubmit={handleSubmit}
          placeholder="Type a message... (/ for commands)"
          focus={isActive}
        />
      </Box>
    </Box>
  );
});

import { Box, Text, useInput } from "ink";
import TextInput from "ink-text-input";
import { type ReactNode, useState, useCallback } from "react";
import { useApp } from "../state/AppContext.js";
import { useInputHistory } from "../hooks/useInputHistory.js";
import { SlashCommands } from "./SlashCommands.js";

type InputMode = "normal" | "multiline" | "shell" | "command" | "search";

interface InputAreaProps {
  onSubmit?: (text: string) => void;
  onCommand?: (command: string, args: string) => void;
  isActive?: boolean;
}

export function InputArea({ onSubmit, onCommand, isActive = true }: InputAreaProps): ReactNode {
  const { dispatch } = useApp();
  const [value, setValue] = useState("");
  const [mode, setMode] = useState<InputMode>("normal");
  const [multilineBuffer, setMultilineBuffer] = useState<string[]>([]);
  const history = useInputHistory();

  const handleSubmit = useCallback((text: string) => {
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

    if (onSubmit) {
      onSubmit(text);
    } else {
      dispatch({
        type: "ADD_MESSAGE",
        message: {
          id: `msg_${Date.now()}`,
          role: "user",
          content: text,
          timestamp: Date.now(),
          isStreaming: false,
        },
      });
    }

    setValue("");
    setMode("normal");
    setMultilineBuffer([]);
  }, [dispatch, history, onSubmit, onCommand]);

  const handleSlashSelect = useCallback((command: string, args: string) => {
    if (onCommand) {
      onCommand(`/${command}`, args);
    }
    setValue("");
    setMode("normal");
  }, [onCommand]);

  const handleSlashDismiss = useCallback(() => {
    setMode("normal");
  }, []);

  const handleChange = useCallback((newValue: string) => {
    setValue(newValue);

    if (newValue.length === 1) {
      if (newValue === "/") {
        setMode("command");
        return;
      }
      if (newValue === "!") {
        setMode("shell");
        return;
      }
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

  const modeLabel = mode === "normal" ? "" :
    mode === "multiline" ? "[Multi-line] " :
    mode === "shell" ? "[Shell] " :
    mode === "command" ? "[Command] " :
    mode === "search" ? "[Search] " : "";

  return (
    <Box flexDirection="column" borderStyle="single" borderColor="gray" paddingX={1}>
      <SlashCommands
        input={value}
        isActive={mode === "command"}
        onSelect={handleSlashSelect}
        onDismiss={handleSlashDismiss}
      />
      {mode === "multiline" && multilineBuffer.length > 0 && (
        <Box flexDirection="column">
          {multilineBuffer.map((line, i) => (
            <Text key={i} dimColor>{line}</Text>
          ))}
        </Box>
      )}
      {mode !== "normal" && (
        <Text color="cyan">{modeLabel.trim()}</Text>
      )}
      <Box>
        <Text color="cyan">&gt; </Text>
        <TextInput
          value={value}
          onChange={handleChange}
          onSubmit={handleSubmit}
          placeholder="Type your message..."
          focus={isActive}
        />
      </Box>
      {value.length > 0 && (
        <Box justifyContent="flex-end">
          <Text dimColor>{value.length} chars</Text>
        </Box>
      )}
    </Box>
  );
}

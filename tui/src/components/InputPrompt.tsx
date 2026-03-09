import { Box, Text, useInput } from "ink";
import TextInput from "ink-text-input";
import {
  type ReactNode,
  useState,
  useCallback,
  useImperativeHandle,
  forwardRef,
  type Ref,
  useRef,
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
  const [inputInstanceKey, setInputInstanceKey] = useState(0);
  const history = useInputHistory();
  const ignoredControlInputRef = useRef<string | null>(null);
  const suppressSubmitRef = useRef(false);

  useImperativeHandle(ref, () => ({
    clear: () => {
      setValue("");
      setMode("normal");
    },
    hasValue: () => value !== "",
  }));

  const handleSubmit = useCallback(
    (text: string) => {
      if (suppressSubmitRef.current) {
        suppressSubmitRef.current = false;
        return;
      }

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

  const insertNewline = useCallback(() => {
    setValue((current) => `${current}\n`);
    // Remount TextInput so its internal cursor lands at the new end position.
    setInputInstanceKey((current) => current + 1);
  }, []);

  const handleChange = useCallback((newValue: string) => {
    const ignoredControlInput = ignoredControlInputRef.current;
    if (
      ignoredControlInput
      && newValue.length === value.length + 1
      && newValue.endsWith(ignoredControlInput)
      && newValue.slice(0, -1) === value
    ) {
      ignoredControlInputRef.current = null;
      return;
    }

    ignoredControlInputRef.current = null;
    setValue(newValue);

    if (newValue.length === 1 && newValue === "/") {
      setMode("command");
      return;
    }

    if (newValue === "") {
      setMode("normal");
    }
  }, [value]);

  const handleInput = useCallback((input: string, key: { [key: string]: boolean }) => {
    if (!isActive) return;

    if (key.ctrl && input) {
      ignoredControlInputRef.current = input;
      suppressSubmitRef.current = input === "j";
    }

    if (key.ctrl && input === "j") {
      insertNewline();
      return;
    }

    if (key.pageUp && mode === "normal") {
      const entry = history.navigateUp();
      if (entry !== undefined) {
        setValue(entry);
      }
      return;
    }

    if (key.pageDown && mode === "normal") {
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
  }, [history, insertNewline, isActive, mode]);

  useInput(handleInput);

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
          key={inputInstanceKey}
          value={value}
          onChange={handleChange}
          onSubmit={handleSubmit}
          placeholder="Type a message... (/ for commands, Ctrl+J newline)"
          focus={isActive}
        />
      </Box>
    </Box>
  );
});

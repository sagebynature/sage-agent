import { Box, Text } from "ink";
import type { ReactNode } from "react";
import { defaultKeybindings } from "../config/keybindings.js";
import type { ShortcutCategory } from "../types/shortcuts.js";

export interface KeyboardHelpProps {
  visible: boolean;
  onClose: () => void;
}

const CATEGORY_LABELS: Record<ShortcutCategory, string> = {
  navigation: "Navigation",
  session: "Session",
  view: "View",
  input: "Input",
  agent: "Agent",
  leader: "Leader",
};

const CATEGORY_ORDER: ShortcutCategory[] = [
  "navigation",
  "session",
  "view",
  "input",
  "agent",
  "leader",
];

function formatKey(kb: (typeof defaultKeybindings)[number]): string {
  const parts: string[] = [];
  if (kb.ctrl) parts.push("Ctrl");
  if (kb.shift) parts.push("Shift");
  if (kb.meta) parts.push("Alt");
  parts.push(kb.key);
  return parts.join("+");
}

export function KeyboardHelp({ visible, onClose: _onClose }: KeyboardHelpProps): ReactNode {
  if (!visible) return null;

  return (
    <Box flexDirection="column" padding={1} borderStyle="round">
      <Box marginBottom={1}>
        <Text bold underline>
          Keyboard Shortcuts
        </Text>
      </Box>

      {CATEGORY_ORDER.map((category) => {
        const bindings = defaultKeybindings.filter((kb) => kb.category === category);
        if (bindings.length === 0) return null;

        return (
          <Box key={category} flexDirection="column" marginBottom={1}>
            <Text bold color="cyan">
              {CATEGORY_LABELS[category]}
            </Text>
            {bindings.map((kb) => (
              <Box key={`${category}-${kb.action}`} flexDirection="row">
                <Box width={20}>
                  <Text color="yellow">{formatKey(kb)}</Text>
                </Box>
                <Text>{kb.description}</Text>
              </Box>
            ))}
          </Box>
        );
      })}

      <Box marginTop={1}>
        <Text dimColor>Press ESC or Ctrl+C to close</Text>
      </Box>
    </Box>
  );
}

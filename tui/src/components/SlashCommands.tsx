import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Box, Text, useInput } from 'ink';
import { commandRegistry } from '../commands/registry.js';

export interface SlashCommandsProps {
  input: string;
  isActive: boolean;
  onSelect: (command: string, args: string) => void;
  onDismiss: () => void;
}

const MAX_VISIBLE_ITEMS = 5;

export const SlashCommands: React.FC<SlashCommandsProps> = ({
  input,
  isActive,
  onSelect,
  onDismiss,
}) => {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const selectedIndexRef = useRef(0);

  const query = input.startsWith('/') ? input.slice(1) : '';

  const filteredCommands = useMemo(() => {
    return commandRegistry.search(query);
  }, [query]);

  useEffect(() => {
    setSelectedIndex(0);
    selectedIndexRef.current = 0;
  }, [filteredCommands.length, query]);

  useInput((_input, key) => {
    if (!isActive) return;

    if (key.escape) {
      onDismiss();
      return;
    }

    if (key.upArrow) {
      const nextIndex = selectedIndexRef.current > 0
        ? selectedIndexRef.current - 1
        : filteredCommands.length - 1;
      selectedIndexRef.current = nextIndex;
      setSelectedIndex(nextIndex);
      return;
    }

    if (key.downArrow) {
      const nextIndex = selectedIndexRef.current < filteredCommands.length - 1
        ? selectedIndexRef.current + 1
        : 0;
      selectedIndexRef.current = nextIndex;
      setSelectedIndex(nextIndex);
      return;
    }

    if (key.return || key.tab) {
      const selected = filteredCommands[selectedIndexRef.current];
      if (selected) {
        onSelect(selected.name, '');
      }
      return;
    }
  }, { isActive });

  if (!isActive || !input.startsWith('/') || filteredCommands.length === 0) {
    return null;
  }

  let startIndex = 0;
  if (filteredCommands.length > MAX_VISIBLE_ITEMS) {
    if (selectedIndex >= MAX_VISIBLE_ITEMS) {
      startIndex = selectedIndex - MAX_VISIBLE_ITEMS + 1;
    }
  }
  const visibleCommands = filteredCommands.slice(startIndex, startIndex + MAX_VISIBLE_ITEMS);

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor="blue"
      paddingX={1}
      width="100%"
    >
      {visibleCommands.map((cmd, index) => {
        const actualIndex = startIndex + index;
        const isSelected = actualIndex === selectedIndex;

        return (
          <Box key={cmd.name} gap={2}>
            <Box width={20}>
              <CommandName
                name={cmd.name}
                query={query}
                isSelected={isSelected}
              />
            </Box>
            <Box flexGrow={1}>
              <Text color={isSelected ? 'black' : 'gray'} backgroundColor={isSelected ? 'white' : undefined}>
                {cmd.description}
              </Text>
            </Box>
          </Box>
        );
      })}
    </Box>
  );
};

const CommandName: React.FC<{ name: string; query: string; isSelected: boolean }> = ({
  name,
  query,
  isSelected
}) => {
  if (!query) {
    return (
      <Text
        color={isSelected ? 'black' : 'cyan'}
        backgroundColor={isSelected ? 'white' : undefined}
        bold={isSelected}
      >
        /{name}
      </Text>
    );
  }

  const lowerName = name.toLowerCase();
  const lowerQuery = query.toLowerCase();
  const matchIndex = lowerName.indexOf(lowerQuery);

  if (matchIndex === -1) {
     return (
      <Text
        color={isSelected ? 'black' : 'cyan'}
        backgroundColor={isSelected ? 'white' : undefined}
        bold={isSelected}
      >
        /{name}
      </Text>
    );
  }

  const before = name.slice(0, matchIndex);
  const match = name.slice(matchIndex, matchIndex + query.length);
  const after = name.slice(matchIndex + query.length);

  return (
    <Text backgroundColor={isSelected ? 'white' : undefined}>
      <Text color={isSelected ? 'black' : 'cyan'}>/</Text>
      <Text color={isSelected ? 'black' : 'cyan'}>{before}</Text>
      <Text color={isSelected ? 'black' : 'cyan'} underline bold>{match}</Text>
      <Text color={isSelected ? 'black' : 'cyan'}>{after}</Text>
    </Text>
  );
};

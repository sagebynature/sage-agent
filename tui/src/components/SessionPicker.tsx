import { useState, useMemo } from 'react';
import { Box, Text, useInput } from 'ink';
import TextInput from 'ink-text-input';
import type { SessionInfo } from '../types/protocol.js';
import { SessionPreview } from './SessionPreview.js';

interface SessionPickerProps {
  sessions: SessionInfo[];
  onResume: (id: string) => void;
  onFork: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
  onClose: () => void;
  currentSessionId?: string;
}

export function SessionPicker({
  sessions,
  onResume,
  onFork,
  onDelete,
  onNew,
  onClose,
  currentSessionId,
}: SessionPickerProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isSearchFocused, setIsSearchFocused] = useState(false);

  const filteredSessions = useMemo(() => {
    const sorted = [...sessions].sort((a, b) => {
        return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
    });

    if (!searchQuery) return sorted;

    const lowerQuery = searchQuery.toLowerCase();
    return sorted.filter(
      (s) =>
        s.id.toLowerCase().includes(lowerQuery) ||
        (s.firstMessage && s.firstMessage.toLowerCase().includes(lowerQuery)) ||
        s.agentName.toLowerCase().includes(lowerQuery)
    );
  }, [sessions, searchQuery]);

  if (selectedIndex >= filteredSessions.length && filteredSessions.length > 0) {
    setSelectedIndex(filteredSessions.length - 1);
  }

  const selectedSession = filteredSessions[selectedIndex];

  useInput((input, key) => {
    if (isSearchFocused) {
      if (key.escape || key.return) {
        setIsSearchFocused(false);
      }
      return;
    }

    if (showDeleteConfirm) {
      if (input.toLowerCase() === 'y' || key.return) {
        if (selectedSession) {
            onDelete(selectedSession.id);
            setShowDeleteConfirm(false);
        }
      } else if (input.toLowerCase() === 'n' || key.escape) {
        setShowDeleteConfirm(false);
      }
      return;
    }

    if (key.upArrow) {
      setSelectedIndex((prev) => Math.max(0, prev - 1));
    } else if (key.downArrow) {
      setSelectedIndex((prev) => Math.min(filteredSessions.length - 1, prev + 1));
    } else if (key.return) {
      if (selectedSession) onResume(selectedSession.id);
    } else if (input === 'f' && selectedSession) {
      onFork(selectedSession.id);
    } else if (input === 'd' && selectedSession) {
       if (selectedSession.id !== currentSessionId) {
          setShowDeleteConfirm(true);
       }
    } else if (input === 'n') {
      onNew();
    } else if (key.escape) {
      onClose();
    } else if (input === '/') {
      setIsSearchFocused(true);
    }
  });

  const relativeTime = (dateString: string) => {
      try {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now.getTime() - date.getTime();
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 0) return `${days}d ago`;
        if (hours > 0) return `${hours}h ago`;
        if (minutes > 0) return `${minutes}m ago`;
        return 'just now';
      } catch {
        return 'unknown';
      }
  };

  if (showDeleteConfirm && selectedSession) {
      return (
          <Box
            width="100%"
            height="100%"
            alignItems="center"
            justifyContent="center"
            borderStyle="double"
            borderColor="red"
            flexDirection="column"
          >
              <Text bold color="red" backgroundColor="black"> DELETE SESSION </Text>
              <Box marginY={1}>
                <Text>Are you sure you want to delete session </Text>
                <Text bold color="yellow">"{selectedSession.id}"</Text>
                <Text>?</Text>
              </Box>
              <Text color="gray">(y/n)</Text>
          </Box>
      );
  }

  const VIEWPORT_HEIGHT = 15;
  const start = Math.max(0, Math.min(selectedIndex - Math.floor(VIEWPORT_HEIGHT / 2), filteredSessions.length - VIEWPORT_HEIGHT));
  const safeStart = Math.max(0, start);
  const end = Math.min(safeStart + VIEWPORT_HEIGHT, filteredSessions.length);
  const visibleSessions = filteredSessions.slice(safeStart, end);

  return (
    <Box flexDirection="row" width="100%" height="100%" borderStyle="single" borderColor="gray">
      <Box flexDirection="column" width="50%" borderStyle="single" borderColor="gray">
        <Box paddingX={1} borderStyle="single" borderColor={isSearchFocused ? "green" : "gray"} marginBottom={1}>
           <Text color={isSearchFocused ? "green" : "gray"}>Search: </Text>
           <TextInput
             value={searchQuery}
             onChange={setSearchQuery}
             placeholder={isSearchFocused ? "Type to filter..." : "Press '/' to search"}
             focus={isSearchFocused}
           />
        </Box>

        <Box flexDirection="column" flexGrow={1}>
            {filteredSessions.length === 0 ? (
                <Box justifyContent="center" alignItems="center" height="100%" flexDirection="column">
                    <Text color="gray">No sessions found.</Text>
                    <Text color="gray">Press 'n' for new session.</Text>
                </Box>
            ) : (
                visibleSessions.map((session, index) => {
                    const realIndex = safeStart + index;
                    const isSelected = realIndex === selectedIndex;
                    const isCurrent = session.id === currentSessionId;

                    return (
                        <Box key={session.id} paddingX={1} borderStyle={isSelected ? "round" : undefined} borderColor={isSelected ? "green" : undefined} marginBottom={0}>
                            <Box flexDirection="column" width="100%">
                                <Box justifyContent="space-between">
                                    <Text color={isSelected ? "green" : (isCurrent ? "yellow" : "white")} bold={isSelected}>
                                        {isSelected ? "> " : "  "}
                                        {session.id.length > 20 ? session.id.slice(0, 20) + '...' : session.id}
                                    </Text>
                                    <Text color="gray">{relativeTime(session.updatedAt)}</Text>
                                </Box>
                                <Text color="gray" wrap="truncate">
                                    {session.firstMessage ? (session.firstMessage.length > 45 ? session.firstMessage.slice(0, 45) + '...' : session.firstMessage) : '(No content)'}
                                </Text>
                            </Box>
                        </Box>
                    );
                })
            )}
        </Box>

        <Box paddingX={1} borderStyle="single" borderColor="gray" marginTop={1}>
            <Text color="gray" wrap="truncate">
                {isSearchFocused ? "Enter/Esc: Exit Search" : "Enter: Resume | f: Fork | d: Del | n: New | /: Search"}
            </Text>
        </Box>
      </Box>

      <SessionPreview session={selectedSession || null} />
    </Box>
  );
}

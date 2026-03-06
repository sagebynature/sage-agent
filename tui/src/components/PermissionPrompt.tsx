import React, { useState, useEffect, useMemo } from 'react';
import { Box, Text, useInput } from 'ink';
import TextInput from 'ink-text-input';
import { highlight } from 'cli-highlight';
import type { PermissionState, PermissionDecision } from '../types/state.js';
import { permissionStore } from '../state/permissions.js';

interface PermissionPromptProps {
  request: PermissionState;
  onRespond: (id: string, decision: PermissionDecision, modifiedArgs?: Record<string, unknown>) => void;
}

const HIGH_RISK_TOOLS = ['shell', 'git_commit', 'git_undo'];
const MEDIUM_RISK_TOOLS = ['file_edit', 'file_write'];
const LOW_RISK_TOOLS = ['file_read', 'memory', 'web'];

const getRiskColor = (tool: string, reportedLevel: string): string => {
  if (HIGH_RISK_TOOLS.includes(tool)) return 'red';
  if (MEDIUM_RISK_TOOLS.includes(tool)) return 'yellow';
  if (LOW_RISK_TOOLS.includes(tool)) return 'green';

  switch (reportedLevel) {
    case 'high': return 'red';
    case 'low': return 'green';
    default: return 'yellow';
  }
};

export const PermissionPrompt: React.FC<PermissionPromptProps> = ({ request, onRespond }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState('');
  const [error, setError] = useState<string | null>(null);

  const { tool, arguments: args, riskLevel, id } = request;

  useEffect(() => {
    if (!isEditing && permissionStore.isAutoApproved(tool, args)) {
      onRespond(id, 'allow_session');
    }
  }, [id, tool, args, isEditing, onRespond]);

  const riskColor = useMemo(() => getRiskColor(tool, riskLevel), [tool, riskLevel]);

  useInput((input, key) => {
    if (isEditing) {
      if (key.escape) {
        setIsEditing(false);
        setError(null);
      }
      return;
    }

    if (input === 'y') {
      onRespond(id, 'allow_once');
    } else if (input === 'a') {
      permissionStore.addSessionGrant(tool);
      onRespond(id, 'allow_session');
    } else if (input === 's') {
      permissionStore.addSimilarGrant(tool, args);
      onRespond(id, 'allow_session');
    } else if (input === 'n') {
      onRespond(id, 'deny');
    } else if (input === 'e') {
      setEditValue(JSON.stringify(args, null, 2));
      setIsEditing(true);
    }
  });

  const handleEditSubmit = (value: string) => {
    try {
      const parsed = JSON.parse(value);
      onRespond(id, 'allow_once', parsed);
    } catch (e) {
      setError('Invalid JSON');
    }
  };

  if (isEditing) {
    return (
      <Box flexDirection="column" borderStyle="round" borderColor="blue" padding={1}>
        <Text bold>Edit Arguments (JSON)</Text>
        <Box marginY={1}>
          <TextInput
            value={editValue}
            onChange={setEditValue}
            onSubmit={handleEditSubmit}
          />
        </Box>
        {error && <Text color="red">{error}</Text>}
        <Text color="gray">Press Enter to submit, Esc to cancel</Text>
      </Box>
    );
  }

  const formattedArgs = highlight(JSON.stringify(args, null, 2), {
    language: 'json',
    ignoreIllegals: true,
  });

  return (
    <Box flexDirection="column" borderStyle="round" borderColor={riskColor} padding={1}>
      <Box marginBottom={1}>
        <Text bold color={riskColor}>PERMS REQUEST: </Text>
        <Text bold>{tool}</Text>
      </Box>

      <Box marginBottom={1}>
        <Text>{formattedArgs}</Text>
      </Box>

      <Box>
        <Text color="gray">
          [y] Allow Once  [a] Allow Session  [s] Allow Similar  [n] Deny  [e] Edit
        </Text>
      </Box>
    </Box>
  );
};

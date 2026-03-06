import React, { useMemo } from 'react';
import { Box, Text } from 'ink';
import { useApp } from '../state/AppContext.js';
import { AgentNode as AgentNodeType } from '../types/state.js';
import { COLORS } from '../theme/colors.js';

interface AgentTreeProps {
  maxDepth?: number;
  showToolDetail?: boolean;
}

const TRUNCATE_LENGTH = 40;

const StatusIndicator = ({ status }: { status: AgentNodeType['status'] }) => {
  if (status === 'active') {
    return <Text color={COLORS.idle}>●</Text>;
  }
  if (status === 'completed') {
    return <Text color="green">✓</Text>;
  }
  if (status === 'failed') {
    return <Text color={COLORS.error}>✗</Text>;
  }
  return <Text color={COLORS.dimmed}>◌</Text>;
};

const TreeNode = ({
  node,
  isLast,
  prefix,
  depth,
  maxDepth
}: {
  node: AgentNodeType;
  isLast: boolean;
  prefix: string;
  depth: number;
  maxDepth: number;
}) => {
  const displayTask = node.task
    ? (node.task.length > TRUNCATE_LENGTH ? node.task.substring(0, TRUNCATE_LENGTH) + '...' : node.task)
    : '';

  let durationStr = '';
  if (node.startedAt) {
    const end = node.completedAt || Date.now();
    const durationMs = end - node.startedAt;
    if (durationMs > 1000) {
      durationStr = `${(durationMs / 1000).toFixed(1)}s`;
    }
  }

  const isBackground = false;

  const connector = isLast ? '└── ' : '├── ';
  const childPrefix = prefix + (isLast ? '    ' : '│   ');

  const showChildren = depth < maxDepth && node.children && node.children.length > 0;

  return (
    <Box flexDirection="column">
      <Box>
        <Text color={COLORS.dimmed}>{prefix}{connector}</Text>
        <Box marginRight={1}>
          <StatusIndicator status={node.status} />
        </Box>
        <Text bold>{isBackground ? '⚡ ' : ''}{node.name}</Text>
        {displayTask && (
          <Text color={COLORS.dimmed}> {displayTask}</Text>
        )}
        {durationStr && node.status !== 'idle' && (
          <Text color={COLORS.dimmed} dimColor> ({durationStr})</Text>
        )}
      </Box>
      {showChildren && node.children.map((child, index) => (
        <TreeNode
          key={child.name}
          node={child}
          isLast={index === node.children.length - 1}
          prefix={childPrefix}
          depth={depth + 1}
          maxDepth={maxDepth}
        />
      ))}
    </Box>
  );
};

export const AgentTree: React.FC<AgentTreeProps> = ({ maxDepth = 5, showToolDetail = false }) => {
  void showToolDetail;
  const { state } = useApp();
  const { agents } = state;

  const rootNodes = useMemo(() => {
    if (!agents || agents.length === 0) return [];

    const agentMap = new Map<string, AgentNodeType>();
    agents.forEach(agent => {
      agentMap.set(agent.name, { ...agent, children: [] });
    });

    const roots: AgentNodeType[] = [];

    agents.forEach(originalAgent => {
      const agent = agentMap.get(originalAgent.name)!;
      if (agent.parentName && agentMap.has(agent.parentName)) {
        agentMap.get(agent.parentName)!.children.push(agent);
      } else {
        roots.push(agent);
      }
    });

    return roots;
  }, [agents]);

  if (rootNodes.length === 0) {
    return null;
  }

  return (
    <Box flexDirection="column">
      {rootNodes.map((node, index) => (
        <TreeNode
          key={node.name}
          node={node}
          isLast={index === rootNodes.length - 1}
          prefix=""
          depth={1}
          maxDepth={maxDepth}
        />
      ))}
    </Box>
  );
};

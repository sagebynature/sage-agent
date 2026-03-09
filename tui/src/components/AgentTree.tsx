import React, { useMemo } from 'react';
import { Box, Text } from 'ink';
import { useBlocks } from '../state/BlockContext.js';
import type { AgentNode as AgentNodeType } from '../types/state.js';

interface AgentTreeProps {
  maxDepth?: number;
}

const TRUNCATE_LENGTH = 40;

function nodeKey(node: AgentNodeType): string {
  return node.delegationId ?? node.agentPath?.join('/') ?? `${node.parentName ?? 'root'}:${node.name}`;
}

const StatusIndicator = ({ status }: { status: AgentNodeType['status'] }) => {
  if (status === 'active') {
    return <Text color="yellow">•</Text>;
  }
  if (status === 'completed') {
    return <Text color="green">✓</Text>;
  }
  if (status === 'failed') {
    return <Text color="red">✗</Text>;
  }
  return <Text color="gray">◌</Text>;
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

  const connector = isLast ? '└── ' : '├── ';
  const childPrefix = prefix + (isLast ? '    ' : '│   ');

  const showChildren = depth + 1 < maxDepth && node.children && node.children.length > 0;

  return (
    <Box flexDirection="column">
      <Box>
        <Text color="gray">{prefix}{connector}</Text>
        <Box marginRight={1}>
          <StatusIndicator status={node.status} />
        </Box>
        <Text bold>{node.name}</Text>
        {displayTask && (
          <Text color="gray"> {displayTask}</Text>
        )}
        {durationStr && node.status !== 'idle' && (
          <Text color="gray" dimColor> ({durationStr})</Text>
        )}
      </Box>
      {showChildren && node.children.map((child, index) => (
        <TreeNode
          key={nodeKey(child)}
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

export const AgentTree: React.FC<AgentTreeProps> = ({ maxDepth = 5 }) => {
  const { state } = useBlocks();
  const { agents } = state;

  const rootNodes = useMemo(() => {
    if (!agents || agents.length === 0) return [];

    const agentMap = new Map<string, AgentNodeType>();
    const parentNameMap = new Map<string, AgentNodeType[]>();
    const roots: AgentNodeType[] = [];

    agents.forEach(agent => {
      const node = { ...agent, children: [] };
      agentMap.set(nodeKey(agent), node);
      const bucket = parentNameMap.get(agent.name) ?? [];
      bucket.push(node);
      parentNameMap.set(agent.name, bucket);
    });

    agents.forEach(originalAgent => {
      const agent = agentMap.get(nodeKey(originalAgent))!;
      const parentPath = originalAgent.agentPath?.slice(0, -1).join('/');
      const parent = (parentPath ? agentMap.get(parentPath) : undefined)
        ?? (originalAgent.parentName ? parentNameMap.get(originalAgent.parentName)?.[0] : undefined);
      if (parent) {
        parent.children.push(agent);
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
          key={nodeKey(node)}
          node={node}
          isLast={index === rootNodes.length - 1}
          prefix=""
          depth={0}
          maxDepth={maxDepth}
        />
      ))}
    </Box>
  );
};

import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import React from 'react';
import type { ToolCallState } from '../types/state.js';
import { ToolTimer } from './ToolTimer.js';
import { ToolCallCollapsible } from './ToolCallCollapsible.js';

interface ToolDisplayProps {
  tool: ToolCallState;
  defaultExpanded?: boolean;
}

const getToolCategory = (name: string): string => {
  if (name.startsWith('git_')) return 'git';
  if (name.startsWith('mcp_')) return 'mcp';
  const map: Record<string, string> = {
    shell: 'shell',
    file_read: 'file_read',
    file_write: 'file_write',
    file_edit: 'file_edit',
    http_request: 'http',
    delegate: 'delegation',
    delegate_background: 'background_task',
    memory_store: 'memory',
    memory_recall: 'memory',
  };
  return map[name] || 'default';
};

const truncateLines = (text: string, maxLines: number) => {
  const lines = text.split('\n');
  if (lines.length <= maxLines) return text;
  return [
    ...lines.slice(0, Math.ceil(maxLines / 2)),
    `... (${lines.length - maxLines} more lines) ...`,
    ...lines.slice(-Math.floor(maxLines / 2))
  ].join('\n');
};

const FormatArgs = ({ args }: { args: Record<string, unknown> }) => {
  return (
    <Box flexDirection="column">
      {Object.entries(args).map(([key, value]) => {
        let displayValue = String(value);
        if (key === 'content' && typeof value === 'string') {
          displayValue = truncateLines(value, 5);
        } else if (typeof value === 'object') {
          displayValue = JSON.stringify(value);
        }
        return (
          <Box key={key}>
            <Text color="cyan">{key}: </Text>
            <Text>{displayValue}</Text>
          </Box>
        );
      })}
    </Box>
  );
};

const ToolDisplayComponent = ({ tool, defaultExpanded }: ToolDisplayProps) => {
  const { status, name, startedAt, completedAt, result, error, arguments: args } = tool;
  const category = getToolCategory(name);

  if (status === 'running' || status === 'pending') {
    return (
      <Box>
        <Text color="yellow"><Spinner type="dots" /> </Text>
        <Text>{name} running... </Text>
        <ToolTimer startTime={startedAt} />
      </Box>
    );
  }

  const isFailed = status === 'failed';
  const icon = isFailed ? <Text color="red">✗</Text> : <Text color="green">✓</Text>;

  const header = (
    <Box>
      <Box marginRight={1}>{icon}</Box>
      <Text bold>{name}</Text>
      <Box marginLeft={1}>
        <ToolTimer startTime={startedAt} endTime={completedAt} />
      </Box>
    </Box>
  );

  const renderContent = () => {
    if (isFailed) {
       return <Text color="red">{error}</Text>;
    }

    if (category === 'file_write') {
      const path = args['path'] as string;
      const size = (args['content'] as string)?.length || 0;
      return (
        <Box flexDirection="column">
           <Text>Writing to <Text bold>{path}</Text> ({size} bytes)</Text>
           <Text dimColor>{truncateLines(args['content'] as string || '', 5)}</Text>
        </Box>
      );
    }

    if (category === 'file_edit') {
       return (
        <Box flexDirection="column">
           <Text>Editing <Text bold>{args['path'] as string}</Text></Text>
           <FormatArgs args={args} />
        </Box>
       );
    }

    if (category === 'shell') {
      const output = result || '';
      return (
        <Box flexDirection="column">
          <Text dimColor>$ {args['command'] as string}</Text>
          <Text>{truncateLines(output, 10)}</Text>
        </Box>
      );
    }

    if (category === 'http') {
       return (
         <Box flexDirection="column">
           <Text>{args['method'] as string} {args['url'] as string}</Text>
           <Text>{truncateLines(result || '', 10)}</Text>
         </Box>
       );
    }

    if (category === 'delegation') {
       return (
         <Box flexDirection="column">
            <Text>Delegating to <Text bold color="magenta">{args['agent_name'] as string || args['agent'] as string}</Text></Text>
            <Text dimColor>Task: {args['task'] as string}</Text>
            <Box paddingLeft={2} borderStyle="single" borderColor="dim">
                <Text dimColor>{truncateLines(result || '', 10)}</Text>
            </Box>
         </Box>
       );
    }

    if (category === 'background_task') {
       return (
          <Box flexDirection="column">
            <Text>Background Task ID: {result}</Text>
            <Text>Agent: {args['agent_name'] as string}</Text>
          </Box>
       );
    }

    if (category === 'memory') {
       const key = args['key'] || args['query'];
       return (
          <Box flexDirection="column">
             <Text>{name === 'memory_store' ? 'Stored' : 'Recalled'}: {key as string}</Text>
             <Text dimColor>{truncateLines(result || '', 5)}</Text>
          </Box>
       );
    }

    if (category === 'git') {
       return (
          <Box flexDirection="column">
             <FormatArgs args={args} />
             <Text>{truncateLines(result || '', 5)}</Text>
          </Box>
       );
    }

    if (category === 'mcp') {
      return (
         <Box flexDirection="column">
            <FormatArgs args={args} />
            <Text>{truncateLines(result || '', 5)}</Text>
         </Box>
      );
    }

    return (
      <Box flexDirection="column">
        <FormatArgs args={args} />
        <Box marginTop={1}>
            <Text dimColor>Result:</Text>
            <Text>{truncateLines(result || '', 10)}</Text>
        </Box>
      </Box>
    );
  };

  return (
    <ToolCallCollapsible
      title={header}
      isFailed={isFailed}
      defaultExpanded={defaultExpanded || isFailed}
    >
      {renderContent()}
    </ToolCallCollapsible>
  );
};

export const ToolDisplay = React.memo(ToolDisplayComponent, (previous, next) => {
  return (
    previous.defaultExpanded === next.defaultExpanded &&
    previous.tool.id === next.tool.id &&
    previous.tool.status === next.tool.status &&
    previous.tool.result === next.tool.result &&
    previous.tool.error === next.tool.error &&
    previous.tool.startedAt === next.tool.startedAt &&
    previous.tool.completedAt === next.tool.completedAt &&
    previous.tool.arguments === next.tool.arguments
  );
});

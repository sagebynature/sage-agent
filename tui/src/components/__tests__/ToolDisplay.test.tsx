import { render } from 'ink-testing-library';
import { describe, it, expect } from 'vitest';
import { ToolDisplay } from '../ToolDisplay.js';
import type { ToolCallState } from '../../types/state.js';

const mockTool = (overrides: Partial<ToolCallState>): ToolCallState => ({
  id: '1',
  name: 'test_tool',
  status: 'completed',
  arguments: {},
  ...overrides,
});

describe('ToolDisplay', () => {
  it('renders running state', () => {
    const { lastFrame } = render(<ToolDisplay tool={mockTool({ status: 'running', name: 'shell', startedAt: Date.now() })} />);
    expect(lastFrame()).toContain('shell running...');
    expect(lastFrame()).toMatch(/\d+ms/);
  });

  it('renders completed success state collapsed by default', () => {
    const { lastFrame } = render(<ToolDisplay tool={mockTool({ status: 'completed', name: 'shell' })} />);
    expect(lastFrame()).toContain('✓');
    expect(lastFrame()).toContain('shell');
  });

  it('renders failed state expanded', () => {
    const error = 'Something went wrong';
    const { lastFrame } = render(<ToolDisplay tool={mockTool({ status: 'failed', error })} />);
    expect(lastFrame()).toContain('✗');
    expect(lastFrame()).toContain(error);
  });

  it('renders file_write', () => {
    const tool = mockTool({
      name: 'file_write',
      arguments: { path: '/tmp/test', content: 'hello world' }
    });
    const { lastFrame } = render(<ToolDisplay tool={tool} defaultExpanded={true} />);
    expect(lastFrame()).toContain('Writing to /tmp/test');
    expect(lastFrame()).toContain('hello world');
  });

  it('renders file_edit', () => {
    const tool = mockTool({
      name: 'file_edit',
      arguments: { path: '/tmp/test', old_string: 'foo', new_string: 'bar' }
    });
    const { lastFrame } = render(<ToolDisplay tool={tool} defaultExpanded={true} />);
    expect(lastFrame()).toContain('Editing /tmp/test');
    expect(lastFrame()).toContain('foo');
  });

  it('renders shell command', () => {
    const tool = mockTool({
      name: 'shell',
      arguments: { command: 'ls -la' },
      result: 'file1\nfile2'
    });
    const { lastFrame } = render(<ToolDisplay tool={tool} defaultExpanded={true} />);
    expect(lastFrame()).toContain('$ ls -la');
    expect(lastFrame()).toContain('file1');
  });

  it('renders http_request', () => {
    const tool = mockTool({
      name: 'http_request',
      arguments: { method: 'GET', url: 'https://example.com' },
      result: '<html>...</html>'
    });
    const { lastFrame } = render(<ToolDisplay tool={tool} defaultExpanded={true} />);
    expect(lastFrame()).toContain('GET https://example.com');
  });

  it('renders delegation', () => {
    const tool = mockTool({
      name: 'delegate',
      arguments: { agent: 'researcher', task: 'find facts' },
      result: 'Found facts'
    });
    const { lastFrame } = render(<ToolDisplay tool={tool} defaultExpanded={true} />);
    expect(lastFrame()).toContain('Delegating to researcher');
    expect(lastFrame()).toContain('Task: find facts');
  });

  it('renders background_task', () => {
    const tool = mockTool({
      name: 'delegate_background',
      arguments: { agent_name: 'helper' },
      result: 'task_123'
    });
    const { lastFrame } = render(<ToolDisplay tool={tool} defaultExpanded={true} />);
    expect(lastFrame()).toContain('Background Task ID: task_123');
    expect(lastFrame()).toContain('Agent: helper');
  });

  it('renders memory operation', () => {
    const tool = mockTool({
      name: 'memory_store',
      arguments: { key: 'user_pref', value: 'dark_mode' },
      result: 'Stored successfully'
    });
    const { lastFrame } = render(<ToolDisplay tool={tool} defaultExpanded={true} />);
    expect(lastFrame()).toContain('Stored: user_pref');
  });

  it('renders git operation', () => {
    const tool = mockTool({
      name: 'git_status',
      arguments: {},
      result: 'On branch main'
    });
    const { lastFrame } = render(<ToolDisplay tool={tool} defaultExpanded={true} />);
    expect(lastFrame()).toContain('On branch main');
  });

  it('renders mcp operation', () => {
    const tool = mockTool({
      name: 'mcp_filesystem',
      arguments: { op: 'list' },
      result: '[]'
    });
    const { lastFrame } = render(<ToolDisplay tool={tool} defaultExpanded={true} />);
    expect(lastFrame()).toContain('op: list');
  });
});

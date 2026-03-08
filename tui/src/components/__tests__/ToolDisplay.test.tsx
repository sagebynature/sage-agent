import { render } from 'ink-testing-library';
import { describe, it, expect } from 'vitest';
import { ToolDisplay } from '../ToolDisplay.js';
import type { ToolSummary } from '../../types/blocks.js';

const mockTool = (overrides: Partial<ToolSummary> = {}): ToolSummary => ({
  name: 'test_tool',
  callId: 'call-1',
  arguments: {},
  status: 'completed',
  ...overrides,
});

describe('ToolDisplay', () => {
  it('renders nothing when tools array is empty', () => {
    const { lastFrame } = render(<ToolDisplay tools={[]} />);
    expect(lastFrame()).toBe('');
  });

  it('renders single completed tool with name', () => {
    const { lastFrame } = render(<ToolDisplay tools={[mockTool({ name: 'shell' })]} />);
    const frame = lastFrame() ?? '';
    expect(frame).toContain('●');
    expect(frame).toContain('shell');
  });

  it('renders single failed tool with error', () => {
    const { lastFrame } = render(
      <ToolDisplay tools={[mockTool({ name: 'shell', status: 'failed', error: 'Permission denied' })]} />
    );
    const frame = lastFrame() ?? '';
    expect(frame).toContain('✗');
    expect(frame).toContain('shell');
    expect(frame).toContain('Permission denied');
  });

  it('renders tool with path argument', () => {
    const { lastFrame } = render(
      <ToolDisplay tools={[mockTool({ name: 'read', arguments: { path: '/tmp/file.txt' } })]} />
    );
    expect(lastFrame()).toContain('/tmp/file.txt');
  });

  it('renders tool with command argument', () => {
    const { lastFrame } = render(
      <ToolDisplay tools={[mockTool({ name: 'shell', arguments: { command: 'ls -la' } })]} />
    );
    expect(lastFrame()).toContain('ls -la');
  });

  it('renders delegate tool with target agent and task preview', () => {
    const { lastFrame } = render(
      <ToolDisplay
        tools={[mockTool({
          name: 'delegate',
          arguments: { agent_name: 'researcher', task: 'compare openfang and openclaw deeply' },
        })]}
      />
    );
    const frame = lastFrame() ?? '';
    expect(frame).toContain('delegate -> researcher');
    expect(frame).toContain('openfang and openclaw');
  });

  it('renders use_skill tool with skill name and loaded preview', () => {
    const { lastFrame } = render(
      <ToolDisplay
        tools={[mockTool({
          name: 'use_skill',
          arguments: { name: 'frontend-developer' },
          result: '# Frontend Developer\nFull instructions here',
        })]}
      />
    );
    const frame = lastFrame() ?? '';
    expect(frame).toContain('use_skill -> frontend-developer');
    expect(frame).toContain('loaded Frontend Developer');
  });

  it('renders tool with duration', () => {
    const { lastFrame } = render(
      <ToolDisplay tools={[mockTool({ name: 'shell', durationMs: 1500 })]} />
    );
    expect(lastFrame()).toContain('1.5s');
  });

  it('renders duration in ms when under 1 second', () => {
    const { lastFrame } = render(
      <ToolDisplay tools={[mockTool({ name: 'read', durationMs: 150 })]} />
    );
    expect(lastFrame()).toContain('150ms');
  });

  it('renders multiple tools of same name as count', () => {
    const tools = [
      mockTool({ name: 'read', callId: 'c1' }),
      mockTool({ name: 'read', callId: 'c2' }),
      mockTool({ name: 'read', callId: 'c3' }),
    ];
    const { lastFrame } = render(<ToolDisplay tools={tools} />);
    expect(lastFrame()).toContain('read (3 calls)');
  });

  it('renders multiple tools of different names as generic count', () => {
    const tools = [
      mockTool({ name: 'read', callId: 'c1' }),
      mockTool({ name: 'write', callId: 'c2' }),
    ];
    const { lastFrame } = render(<ToolDisplay tools={tools} />);
    expect(lastFrame()).toContain('2 tool calls');
  });

  it('shows individual tool status lines for multiple tools', () => {
    const tools = [
      mockTool({ name: 'read', callId: 'c1', arguments: { path: '/a' } }),
      mockTool({ name: 'read', callId: 'c2', status: 'failed', error: 'not found' }),
    ];
    const { lastFrame } = render(<ToolDisplay tools={tools} />);
    const frame = lastFrame() ?? '';
    expect(frame).toContain('✓');
    expect(frame).toContain('✗');
    expect(frame).toContain('not found');
  });
});

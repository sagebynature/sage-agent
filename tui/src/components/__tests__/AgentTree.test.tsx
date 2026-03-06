import { render } from 'ink-testing-library';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AgentTree } from '../AgentTree.js';
import type { AgentNode } from '../../types/state.js';

const mockUseApp = vi.fn();
vi.mock('../../state/AppContext.js', () => ({
  useApp: () => mockUseApp(),
}));

const createAgent = (
  name: string,
  status: AgentNode['status'] = 'idle',
  parentName?: string,
  task?: string
): AgentNode => ({
  name,
  status,
  parentName,
  task,
  depth: parentName ? 1 : 0,
  children: [],
  startedAt: Date.now(),
});

describe('AgentTree', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when there are no agents', () => {
    mockUseApp.mockReturnValue({
      state: { agents: [] },
    });

    const { lastFrame } = render(<AgentTree />);
    expect(lastFrame()).toBe('');
  });

  it('renders a single root agent', () => {
    const agents = [createAgent('root-agent', 'active', undefined, 'Root Task')];
    mockUseApp.mockReturnValue({ state: { agents } });

    const { lastFrame } = render(<AgentTree />);

    expect(lastFrame()).toContain('root-agent');
    expect(lastFrame()).toContain('Root Task');
    expect(lastFrame()).toContain('●');
  });

  it('renders a nested agent hierarchy', () => {
    const agents = [
      createAgent('root', 'active'),
      createAgent('child', 'idle', 'root'),
    ];
    mockUseApp.mockReturnValue({ state: { agents } });

    const { lastFrame } = render(<AgentTree />);

    expect(lastFrame()).toContain('root');
    expect(lastFrame()).toContain('└── ◌ child');
  });

  it('renders multiple children with correct connectors', () => {
    const agents = [
      createAgent('root', 'active'),
      createAgent('child1', 'idle', 'root'),
      createAgent('child2', 'idle', 'root'),
    ];
    mockUseApp.mockReturnValue({ state: { agents } });

    const { lastFrame } = render(<AgentTree />);

    expect(lastFrame()).toContain('├── ◌ child1');
    expect(lastFrame()).toContain('└── ◌ child2');
  });

  it('renders deep nesting', () => {
    const agents = [
      createAgent('root', 'active'),
      createAgent('level1', 'active', 'root'),
      createAgent('level2', 'active', 'level1'),
    ];
    mockUseApp.mockReturnValue({ state: { agents } });

    const { lastFrame } = render(<AgentTree />);

    const frame = lastFrame();
    expect(frame).toContain('root');
    expect(frame).toContain('└── ● level1');
    expect(frame).toContain('└── ● level2');
  });

  it('displays correct status indicators', () => {
    const agents = [
      createAgent('agent-active', 'active'),
      createAgent('agent-completed', 'completed'),
      createAgent('agent-failed', 'failed'),
      createAgent('agent-idle', 'idle'),
    ];
    mockUseApp.mockReturnValue({ state: { agents } });

    const { lastFrame } = render(<AgentTree />);
    const frame = lastFrame() || '';

    expect(frame).toContain('●');
    expect(frame).toContain('✓');
    expect(frame).toContain('✗');
    expect(frame).toContain('◌');
  });

  it('handles background tasks with lightning bolt', () => {
  });

  it('respects maxDepth prop', () => {
    const agents = [
      createAgent('root', 'active'),
      createAgent('level1', 'active', 'root'),
      createAgent('level2', 'active', 'level1'),
      createAgent('level3', 'active', 'level2'),
    ];
    mockUseApp.mockReturnValue({ state: { agents } });

    const { lastFrame } = render(<AgentTree maxDepth={2} />);

    expect(lastFrame()).toContain('root');
    expect(lastFrame()).toContain('level1');
    expect(lastFrame()).not.toContain('level2');
    expect(lastFrame()).not.toContain('level3');
  });

  it('truncates long task summaries', () => {
    const longTask = 'This is a very long task description that should be truncated because it is too long';
    const agents = [createAgent('root', 'active', undefined, longTask)];
    mockUseApp.mockReturnValue({ state: { agents } });

    const { lastFrame } = render(<AgentTree />);

    expect(lastFrame()).not.toContain(longTask);
    expect(lastFrame()).toContain('This is a very long task description tha...');
  });
});

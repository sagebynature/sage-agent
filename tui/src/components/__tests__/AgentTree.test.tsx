import { render } from 'ink-testing-library';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AgentTree } from '../AgentTree.js';
import type { AgentNode } from '../../types/state.js';
import type { BlockState } from '../../state/blockReducer.js';
import { INITIAL_BLOCK_STATE } from '../../state/blockReducer.js';

let mockState: BlockState = { ...INITIAL_BLOCK_STATE };

vi.mock('../../state/BlockContext.js', () => ({
  useBlocks: () => ({ state: mockState, dispatch: vi.fn() }),
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
    mockState = { ...INITIAL_BLOCK_STATE };
  });

  it('renders nothing when there are no agents', () => {
    mockState = { ...INITIAL_BLOCK_STATE, agents: [] };
    const { lastFrame } = render(<AgentTree />);
    expect(lastFrame()).toBe('');
  });

  it('renders a single root agent', () => {
    mockState = { ...INITIAL_BLOCK_STATE, agents: [createAgent('root-agent', 'active', undefined, 'Root Task')] };
    const { lastFrame } = render(<AgentTree />);
    expect(lastFrame()).toContain('root-agent');
    expect(lastFrame()).toContain('Root Task');
    expect(lastFrame()).toContain('●');
  });

  it('renders a nested agent hierarchy', () => {
    mockState = {
      ...INITIAL_BLOCK_STATE,
      agents: [
        createAgent('root', 'active'),
        createAgent('child', 'idle', 'root'),
      ],
    };
    const { lastFrame } = render(<AgentTree />);
    expect(lastFrame()).toContain('root');
    expect(lastFrame()).toContain('└── ◌ child');
  });

  it('renders multiple children with correct connectors', () => {
    mockState = {
      ...INITIAL_BLOCK_STATE,
      agents: [
        createAgent('root', 'active'),
        createAgent('child1', 'idle', 'root'),
        createAgent('child2', 'idle', 'root'),
      ],
    };
    const { lastFrame } = render(<AgentTree />);
    expect(lastFrame()).toContain('├── ◌ child1');
    expect(lastFrame()).toContain('└── ◌ child2');
  });

  it('renders deep nesting', () => {
    mockState = {
      ...INITIAL_BLOCK_STATE,
      agents: [
        createAgent('root', 'active'),
        createAgent('level1', 'active', 'root'),
        createAgent('level2', 'active', 'level1'),
      ],
    };
    const { lastFrame } = render(<AgentTree />);
    const frame = lastFrame();
    expect(frame).toContain('root');
    expect(frame).toContain('└── ● level1');
    expect(frame).toContain('└── ● level2');
  });

  it('displays correct status indicators', () => {
    mockState = {
      ...INITIAL_BLOCK_STATE,
      agents: [
        createAgent('agent-active', 'active'),
        createAgent('agent-completed', 'completed'),
        createAgent('agent-failed', 'failed'),
        createAgent('agent-idle', 'idle'),
      ],
    };
    const { lastFrame } = render(<AgentTree />);
    const frame = lastFrame() || '';
    expect(frame).toContain('●');
    expect(frame).toContain('✓');
    expect(frame).toContain('✗');
    expect(frame).toContain('◌');
  });

  it('handles empty background task case', () => {
    // No-op — background indicator removed in port
  });

  it('respects maxDepth prop', () => {
    mockState = {
      ...INITIAL_BLOCK_STATE,
      agents: [
        createAgent('root', 'active'),
        createAgent('level1', 'active', 'root'),
        createAgent('level2', 'active', 'level1'),
        createAgent('level3', 'active', 'level2'),
      ],
    };
    const { lastFrame } = render(<AgentTree maxDepth={2} />);
    expect(lastFrame()).toContain('root');
    expect(lastFrame()).toContain('level1');
    expect(lastFrame()).not.toContain('level2');
    expect(lastFrame()).not.toContain('level3');
  });

  it('truncates long task summaries', () => {
    const longTask = 'This is a very long task description that should be truncated because it is too long';
    mockState = {
      ...INITIAL_BLOCK_STATE,
      agents: [createAgent('root', 'active', undefined, longTask)],
    };
    const { lastFrame } = render(<AgentTree />);
    expect(lastFrame()).not.toContain(longTask);
    expect(lastFrame()).toContain('This is a very long task description tha...');
  });

  it('renders repeated subagent names as separate nodes when paths differ', () => {
    mockState = {
      ...INITIAL_BLOCK_STATE,
      agents: [
        { ...createAgent('root', 'active'), agentPath: ['root'] },
        {
          ...createAgent('worker', 'completed', 'root', 'first task'),
          agentPath: ['root', 'worker'],
          delegationId: 'delegation-1',
        },
        {
          ...createAgent('worker', 'active', 'root', 'second task'),
          agentPath: ['root', 'worker-2'],
          delegationId: 'delegation-2',
        },
      ],
    };

    const { lastFrame } = render(<AgentTree />);
    const frame = lastFrame() || '';
    expect(frame.match(/worker/g)?.length).toBe(2);
    expect(frame).toContain('first task');
    expect(frame).toContain('second task');
  });
});

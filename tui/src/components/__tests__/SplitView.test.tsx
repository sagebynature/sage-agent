import { type ReactNode } from 'react';
import { render } from 'ink-testing-library';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Text, Box } from 'ink';
import { SplitView } from '../SplitView.js';
import { AppProvider } from '../../state/AppContext.js';

// Hoist the mock object creation so it's available in the factory
const { mockStdout } = vi.hoisted(() => {
  const { EventEmitter } = require('events');
  class MockStdout extends EventEmitter {
    columns = 120;
    rows = 40;
    write = () => {};
  }
  return { mockStdout: new MockStdout() };
});

// Mock ink hooks
vi.mock('ink', async () => {
  const original: any = await vi.importActual('ink');
  return {
    ...original,
    useStdout: () => ({
      stdout: mockStdout,
      write: vi.fn(),
    }),
  };
});

// Mock Sidebar components to simplify testing SplitView logic
vi.mock('../sidebar/AgentTab.js', () => ({
  AgentTab: () => <Text>Agent Tab Content</Text>,
}));
vi.mock('../sidebar/UsageTab.js', () => ({
  UsageTab: () => <Text>Usage Tab Content</Text>,
}));
vi.mock('../sidebar/FilesTab.js', () => ({
  FilesTab: () => <Text>Files Tab Content</Text>,
}));
vi.mock('../sidebar/TasksTab.js', () => ({
  TasksTab: () => <Text>Tasks Tab Content</Text>,
}));

const Wrapper = ({ children, width = 200 }: { children: ReactNode; width?: number }) => {
  return (
    <AppProvider>
      <Box width={width} height={40}>
        {children}
      </Box>
    </AppProvider>
  );
};

const mockState: { agents: { name: string; arguments?: Record<string, unknown> }[]; tools: { name: string; arguments: Record<string, unknown> }[] } = {
  agents: [],
  tools: [],
};

vi.mock('../../state/AppContext.js', async () => {
  const actual = await vi.importActual('../../state/AppContext.js');
  return {
    ...actual,
    useApp: () => ({
      state: mockState,
      dispatch: vi.fn(),
    }),
  };
});

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

describe('SplitView', () => {
  beforeEach(() => {
    mockStdout.columns = 200;
    mockStdout.removeAllListeners();
    mockState.agents = [];
    mockState.tools = [];
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders main content and sidebar by default', () => {
    const { lastFrame } = render(
      <Wrapper>
        <SplitView>
          <Text>Main Content</Text>
        </SplitView>
      </Wrapper>
    );

    const output = lastFrame();
    expect(output).toContain('Main Content');
    expect(output).toContain('Agent Tab Content');
  });

  it('collapses sidebar when terminal is too narrow', async () => {
    mockStdout.columns = 80;

    const { lastFrame } = render(
      <Wrapper width={80}>
        <SplitView>
          <Text>Main Content</Text>
        </SplitView>
      </Wrapper>
    );

    await delay(50); // Allow effect to run
    const output = lastFrame();
    expect(output).toContain('Main Content');
    expect(output).not.toContain('Agent Tab Content');
  });

  it('toggles sidebar with Ctrl+B', async () => {
    const { lastFrame, stdin } = render(
      <Wrapper>
        <SplitView>
          <Text>Main Content</Text>
        </SplitView>
      </Wrapper>
    );

    expect(lastFrame()).toContain('Agent Tab Content');

    // Ctrl+B is \x02
    stdin.write('\x02');
    await delay(50);

    expect(lastFrame()).not.toContain('Agent Tab Content');

    stdin.write('\x02');
    await delay(50);

    expect(lastFrame()).toContain('Agent Tab Content');
  });

  it('cycles tabs with Tab key', async () => {
    const { lastFrame, stdin } = render(
      <Wrapper>
        <SplitView>
          <Text>Main Content</Text>
        </SplitView>
      </Wrapper>
    );

    expect(lastFrame()).toContain('Agent Tab Content');

    stdin.write('\t');
    await delay(10);
    expect(lastFrame()).toContain('Usage Tab Content');

    stdin.write('\t');
    await delay(10);
    expect(lastFrame()).toContain('Files Tab Content');

    stdin.write('\t');
    await delay(10);
    expect(lastFrame()).toContain('Tasks Tab Content');

    stdin.write('\t');
    await delay(10);
    expect(lastFrame()).toContain('Agent Tab Content');
  });

  it('shows files badge count', () => {
    // @ts-ignore
    mockState.tools = [
      { name: 'file_read', arguments: { path: 'file1.txt' } },
      { name: 'file_write', arguments: { path: 'file2.txt' } },
      { name: 'file_read', arguments: { path: 'file1.txt' } },
    ];

    const { lastFrame } = render(
      <Wrapper>
        <SplitView>
          <Text>Main Content</Text>
        </SplitView>
      </Wrapper>
    );

    // Should show (2) for 2 distinct files
    expect(lastFrame()).toContain('Files (2)');
  });

  it('shows agents badge count', () => {
    // @ts-ignore
    mockState.agents = [
      { name: 'agent1' },
      { name: 'agent2' },
      { name: 'agent3' },
    ];

    const { lastFrame } = render(
      <Wrapper>
        <SplitView>
          <Text>Main Content</Text>
        </SplitView>
      </Wrapper>
    );

    expect(lastFrame()).toContain('Agent (3)');
  });

  it('hides sidebar when terminal resizes to narrow', async () => {
    const { lastFrame } = render(
      <Wrapper>
        <SplitView>
          <Text>Main Content</Text>
        </SplitView>
      </Wrapper>
    );

    expect(lastFrame()).toContain('Agent Tab Content');

    mockStdout.columns = 90;
    mockStdout.emit('resize');
    await delay(10);

    expect(lastFrame()).not.toContain('Agent Tab Content');
  });

  it('shows sidebar when terminal resizes to wide', async () => {
    mockStdout.columns = 90;
    const { lastFrame } = render(
      <Wrapper>
        <SplitView>
          <Text>Main Content</Text>
        </SplitView>
      </Wrapper>
    );

    await delay(50);
    expect(lastFrame()).not.toContain('Agent Tab Content');

    mockStdout.columns = 150;
    mockStdout.emit('resize');
    await delay(10);

    expect(lastFrame()).toContain('Agent Tab Content');
  });

  it('displays correct tabs list', () => {
    const { lastFrame } = render(
      <Wrapper>
        <SplitView>
          <Text>Main Content</Text>
        </SplitView>
      </Wrapper>
    );

    const output = lastFrame();
    expect(output).toContain('Agent');
    expect(output).toContain('Usage');
    expect(output).toContain('Files');
    expect(output).toContain('Tasks');
  });

  it('handles empty badges correctly', () => {
    mockState.agents = [];
    mockState.tools = [];

    const { lastFrame } = render(
      <Wrapper>
        <SplitView>
          <Text>Main Content</Text>
        </SplitView>
      </Wrapper>
    );

    const output = lastFrame();
    expect(output).not.toContain('Agent (');
    expect(output).not.toContain('Files (');
  });

  it('renders Usage tab content when selected', async () => {
    const { lastFrame, stdin } = render(
      <Wrapper>
        <SplitView>
          <Text>Main Content</Text>
        </SplitView>
      </Wrapper>
    );

    stdin.write('\t');
    await delay(10);
    expect(lastFrame()).toContain('Usage Tab Content');
  });

  it('renders Files tab content when selected', async () => {
    const { lastFrame, stdin } = render(
      <Wrapper>
        <SplitView>
          <Text>Main Content</Text>
        </SplitView>
      </Wrapper>
    );

    stdin.write('\t');
    await delay(10);
    stdin.write('\t');
    await delay(10);
    expect(lastFrame()).toContain('Files Tab Content');
  });

  it('renders Tasks tab content when selected', async () => {
    const { lastFrame, stdin } = render(
      <Wrapper>
        <SplitView>
          <Text>Main Content</Text>
        </SplitView>
      </Wrapper>
    );

    stdin.write('\t');
    await delay(10);
    stdin.write('\t');
    await delay(10);
    stdin.write('\t');
    await delay(10);
    expect(lastFrame()).toContain('Tasks Tab Content');
  });
});

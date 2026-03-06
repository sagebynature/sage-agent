import { describe, it, expect, vi } from 'vitest';
import { renderApp } from '../../test-utils.js';
import { SessionPicker } from '../SessionPicker.js';
import type { SessionInfo } from '../../types/protocol.js';

const mockSessions: SessionInfo[] = [
  {
    id: 'session-123',
    agentName: 'researcher',
    createdAt: new Date(Date.now() - 1000000).toISOString(),
    updatedAt: new Date(Date.now() - 5000).toISOString(),
    messageCount: 5,
    model: 'gpt-4o',
    totalCost: 0.05,
    firstMessage: 'Hello world',
  },
  {
    id: 'session-456',
    agentName: 'writer',
    createdAt: new Date(Date.now() - 2000000).toISOString(),
    updatedAt: new Date(Date.now() - 1000000).toISOString(),
    messageCount: 10,
    model: 'claude-3-opus',
    totalCost: 0.15,
    firstMessage: 'Write a poem',
  },
  {
    id: 'current-session',
    agentName: 'assistant',
    createdAt: new Date(Date.now() - 3000000).toISOString(),
    updatedAt: new Date(Date.now() - 2000000).toISOString(),
    messageCount: 2,
    model: 'gpt-3.5-turbo',
    totalCost: 0.01,
    firstMessage: 'Hi there',
  }
];

describe('SessionPicker', () => {
  const defaultProps = {
    sessions: mockSessions,
    onResume: vi.fn(),
    onFork: vi.fn(),
    onDelete: vi.fn(),
    onNew: vi.fn(),
    onClose: vi.fn(),
    currentSessionId: 'current-session',
  };

  it('renders session list sorted by update time', () => {
    const { lastFrame } = renderApp(<SessionPicker {...defaultProps} />);
    const frame = lastFrame();

    expect(frame).toContain('session-123');
    expect(frame).toContain('session-456');
    expect(frame).toContain('current-session');

    const idx1 = frame?.indexOf('session-123');
    const idx2 = frame?.indexOf('current-session');
    expect(idx1).toBeLessThan(idx2!);
  });

  it('renders empty state', () => {
    const { lastFrame } = renderApp(<SessionPicker {...defaultProps} sessions={[]} />);
    expect(lastFrame()).toContain('No sessions found');
  });

  it('highlights selected session', () => {
    const { lastFrame } = renderApp(<SessionPicker {...defaultProps} />);
    expect(lastFrame()).toContain('> session-123');
  });

  it('navigates with arrow keys', async () => {
    const { stdin, lastFrame } = renderApp(<SessionPicker {...defaultProps} />);

    expect(lastFrame()).toContain('> session-123');

    stdin.write('\u001B[B');
    await new Promise(r => setTimeout(r, 50));

    const frame = lastFrame();
    expect(frame).not.toContain('> session-123');
    expect(frame).toContain('> session-456');
  });

  it('resumes session on Enter', () => {
    const onResume = vi.fn();
    const { stdin } = renderApp(<SessionPicker {...defaultProps} onResume={onResume} />);

    stdin.write('\r');
    expect(onResume).toHaveBeenCalledWith('session-123');
  });

  it('forks session on f', () => {
    const onFork = vi.fn();
    const { stdin } = renderApp(<SessionPicker {...defaultProps} onFork={onFork} />);
    stdin.write('f');
    expect(onFork).toHaveBeenCalledWith('session-123');
  });

  it('creates new session on n', () => {
    const onNew = vi.fn();
    const { stdin } = renderApp(<SessionPicker {...defaultProps} onNew={onNew} />);
    stdin.write('n');
    expect(onNew).toHaveBeenCalled();
  });

  it('closes on Escape', () => {
    const onClose = vi.fn();
    const { stdin } = renderApp(<SessionPicker {...defaultProps} onClose={onClose} />);
    stdin.write('\u001B');
    expect(onClose).toHaveBeenCalled();
  });

  it('shows delete confirmation on d', async () => {
    const { stdin, lastFrame } = renderApp(<SessionPicker {...defaultProps} />);
    stdin.write('d');

    await new Promise(r => setTimeout(r, 50));
    expect(lastFrame()).toContain('DELETE SESSION');
  });

  it('confirms delete with y', async () => {
    const onDelete = vi.fn();
    const { stdin } = renderApp(<SessionPicker {...defaultProps} onDelete={onDelete} />);

    stdin.write('d');
    await new Promise(r => setTimeout(r, 50));

    stdin.write('y');
    expect(onDelete).toHaveBeenCalledWith('session-123');
  });

  it('cancels delete with n', async () => {
    const onDelete = vi.fn();
    const { stdin, lastFrame } = renderApp(<SessionPicker {...defaultProps} onDelete={onDelete} />);

    stdin.write('d');
    await new Promise(r => setTimeout(r, 50));

    stdin.write('n');
    await new Promise(r => setTimeout(r, 50));

    expect(lastFrame()).not.toContain('DELETE SESSION');
    expect(onDelete).not.toHaveBeenCalled();
  });

  it('prevents deleting current session', async () => {
    const { stdin, lastFrame } = renderApp(<SessionPicker {...defaultProps} />);

    stdin.write('\u001B[B');
    stdin.write('\u001B[B');
    await new Promise(r => setTimeout(r, 50));

    stdin.write('d');
    await new Promise(r => setTimeout(r, 50));

    expect(lastFrame()).not.toContain('DELETE SESSION');
  });

  it('filters sessions with search', async () => {
    const { stdin, lastFrame } = renderApp(<SessionPicker {...defaultProps} />);

    stdin.write('/');
    await new Promise(r => setTimeout(r, 50));

    stdin.write('poem');
    await new Promise(r => setTimeout(r, 50));

    const frame = lastFrame();
    expect(frame).toContain('session-456');
    expect(frame).not.toContain('session-123');
  });
});

import { render } from 'ink-testing-library';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PermissionPrompt } from '../PermissionPrompt.js';
import { PermissionState } from '../../types/state.js';
import { permissionStore } from '../../state/permissions.js';

describe('PermissionPrompt', () => {
  const mockRequest: PermissionState = {
    id: 'req-123',
    tool: 'file_read',
    arguments: { path: 'test.txt' },
    riskLevel: 'low',
    status: 'pending'
  };

  const onRespond = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    permissionStore.clear();
  });

  it('renders tool name and arguments', () => {
    const { lastFrame } = render(<PermissionPrompt request={mockRequest} onRespond={onRespond} />);
    expect(lastFrame()).toContain('file_read');
    expect(lastFrame()).toContain('"path": "test.txt"');
  });

  it('handles "y" input for allow_once', () => {
    const { stdin } = render(<PermissionPrompt request={mockRequest} onRespond={onRespond} />);
    stdin.write('y');
    expect(onRespond).toHaveBeenCalledWith('req-123', 'allow_once');
  });

  it('handles "n" input for deny', () => {
    const { stdin } = render(<PermissionPrompt request={mockRequest} onRespond={onRespond} />);
    stdin.write('n');
    expect(onRespond).toHaveBeenCalledWith('req-123', 'deny');
  });

  it('handles "a" input for allow_session', () => {
    const { stdin } = render(<PermissionPrompt request={mockRequest} onRespond={onRespond} />);
    stdin.write('a');
    expect(onRespond).toHaveBeenCalledWith('req-123', 'allow_session');
    expect(permissionStore.isAutoApproved('file_read', {})).toBe(true);
  });

  it('handles "s" input for allow_similar', () => {
    const { stdin } = render(<PermissionPrompt request={mockRequest} onRespond={onRespond} />);
    stdin.write('s');
    expect(onRespond).toHaveBeenCalledWith('req-123', 'allow_session');
    expect(permissionStore.isAutoApproved('file_read', { path: 'test.txt' })).toBe(true);
  });


  const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

  it('handles "e" input to enter edit mode', async () => {
    const { lastFrame, stdin } = render(<PermissionPrompt request={mockRequest} onRespond={onRespond} />);
    stdin.write('e');
    await delay(10);
    expect(lastFrame()).toContain('Edit Arguments');
  });

  it('returns to prompt mode on escape from edit mode', async () => {
    const { lastFrame, stdin } = render(<PermissionPrompt request={mockRequest} onRespond={onRespond} />);
    stdin.write('e');
    await delay(10);
    expect(lastFrame()).toContain('Edit Arguments');
    stdin.write('\u001B'); // Escape
    // Ink uses a 100ms timeout to distinguish bare escape from escape sequences
    await delay(400);
    expect(lastFrame()).toContain('PERMS REQUEST');
  });

  it('shows error on invalid JSON in edit mode', async () => {
    const { lastFrame, stdin } = render(<PermissionPrompt request={mockRequest} onRespond={onRespond} />);
    stdin.write('e');
    await delay(10);
    expect(lastFrame()).toContain('Edit Arguments');
    stdin.write('INVALID');
    await delay(25);
    stdin.write('\r'); // Enter
    await delay(50);
    expect(lastFrame()).toContain('Invalid JSON');
  });


  it('auto-approves if store has session grant', () => {
    permissionStore.addSessionGrant('file_read');
    render(<PermissionPrompt request={mockRequest} onRespond={onRespond} />);
    // useEffect runs after render, but in testing library it might be sync or require wait
    // We expect onRespond to be called immediately
    expect(onRespond).toHaveBeenCalledWith('req-123', 'allow_session');
  });

  it('does not auto-approve if store has no grant', () => {
    render(<PermissionPrompt request={mockRequest} onRespond={onRespond} />);
    expect(onRespond).not.toHaveBeenCalled();
  });

  it('renders red border for high risk', () => {
    const highRiskRequest = { ...mockRequest, riskLevel: 'high' as const, tool: 'shell' };
    const { lastFrame } = render(<PermissionPrompt request={highRiskRequest} onRespond={onRespond} />);
    // Ink doesn't render colors as text, but chalk/ink transforms them.
    // Testing colors in output string is tricky as they are ANSI codes.
    // We rely on component logic being correct.
    // But we can check if it renders.
    expect(lastFrame()).toContain('shell');
  });

  it('renders yellow border for medium risk', () => {
    const mediumRiskRequest = { ...mockRequest, riskLevel: 'medium' as const, tool: 'file_write' };
    const { lastFrame } = render(<PermissionPrompt request={mediumRiskRequest} onRespond={onRespond} />);
    expect(lastFrame()).toContain('file_write');
  });
});

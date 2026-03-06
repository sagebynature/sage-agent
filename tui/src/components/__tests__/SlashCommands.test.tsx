import { describe, it, expect, vi } from 'vitest';
import { render } from 'ink-testing-library';
import { SlashCommands } from '../SlashCommands.js';

describe('SlashCommands', () => {
  const defaultProps = {
    input: '/mod',
    isActive: true,
    onSelect: vi.fn(),
    onDismiss: vi.fn(),
  };

  it('renders nothing when not active', () => {
    const { lastFrame } = render(<SlashCommands {...defaultProps} isActive={false} />);
    expect(lastFrame()).toBe('');
  });

  it('renders nothing when input does not start with /', () => {
    const { lastFrame } = render(<SlashCommands {...defaultProps} input="hello" />);
    expect(lastFrame()).toBe('');
  });

  it('renders nothing when no matches found', () => {
    const { lastFrame } = render(<SlashCommands {...defaultProps} input="/xyz123" />);
    expect(lastFrame()).toBe('');
  });

  it('renders matching commands', () => {
    const { lastFrame } = render(<SlashCommands {...defaultProps} />);
    const output = lastFrame();
    expect(output).toContain('model');
    expect(output).toContain('models');
  });

  it('filters commands based on input', () => {
    const { lastFrame } = render(<SlashCommands {...defaultProps} input="/help" />);
    const output = lastFrame();
    expect(output).toContain('help');
    expect(output).not.toContain('model');
  });

  it('highlights matching characters', () => {
    const { lastFrame } = render(<SlashCommands {...defaultProps} />);
    expect(lastFrame()).toContain('mod');
  });

  it('handles navigation with arrow keys', async () => {
    const { stdin } = render(<SlashCommands {...defaultProps} input="/mod" />);

    stdin.write('\u001B[B');
    await new Promise(resolve => setTimeout(resolve, 10));
    stdin.write('\r');

    expect(defaultProps.onSelect).toHaveBeenCalledWith('models', '');
  });

  it('handles wrapping navigation', async () => {
    const { stdin } = render(<SlashCommands {...defaultProps} input="/mod" />);

    stdin.write('\u001B[A');
    await new Promise(resolve => setTimeout(resolve, 10));
    stdin.write('\r');

    expect(defaultProps.onSelect).toHaveBeenCalledWith('compact', '');
  });

  it('selects command with Tab', () => {
    const { stdin } = render(<SlashCommands {...defaultProps} input="/help" />);
    stdin.write('\t');
    expect(defaultProps.onSelect).toHaveBeenCalledWith('help', '');
  });

  it('dismisses on Escape', () => {
    const { stdin } = render(<SlashCommands {...defaultProps} />);
    stdin.write('\u001B');
    expect(defaultProps.onDismiss).toHaveBeenCalled();
  });

  it('resets selection when query changes', () => {
    const { rerender, stdin } = render(<SlashCommands {...defaultProps} input="/mod" />);

    stdin.write('\u001B[B');

    rerender(<SlashCommands {...defaultProps} input="/help" />);

    stdin.write('\r');
    expect(defaultProps.onSelect).toHaveBeenCalledWith('help', '');
  });
});

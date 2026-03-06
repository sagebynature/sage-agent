import { render } from 'ink-testing-library';
import { describe, it, expect, vi } from 'vitest';
import { DiffDisplay } from '../DiffDisplay.js';
import { DiffBar } from '../DiffBar.js';

vi.mock('ink', async () => {
  const actual = await vi.importActual('ink');
  return {
    ...actual,
    useStdout: () => ({
      stdout: { columns: 100, write: vi.fn() },
    }),
  };
});

describe('DiffBar', () => {
  it('renders correctly with additions and deletions', () => {
    const { lastFrame } = render(<DiffBar additions={10} deletions={5} />);
    const frame = lastFrame();
    expect(frame).toContain('+10');
    expect(frame).toContain('-5');
    expect(frame).toContain('█');
  });

  it('renders "No changes" when total is 0', () => {
    const { lastFrame } = render(<DiffBar additions={0} deletions={0} />);
    expect(lastFrame()).toContain('No changes');
  });
});

describe('DiffDisplay', () => {
  it('renders inline diff correctly', () => {
    const oldContent = 'line1\nline2\nline3';
    const newContent = 'line1\nline2 modified\nline3';
    const { lastFrame } = render(
      <DiffDisplay oldContent={oldContent} newContent={newContent} mode="inline" />
    );
    const frame = lastFrame();
    expect(frame).toContain('line1');
    expect(frame).toContain('- line2');
    expect(frame).toContain('+ line2 modified');
    expect(frame).toContain('line3');
  });

  it('renders side-by-side diff correctly', () => {
    const oldContent = 'line1\nline2\nline3';
    const newContent = 'line1\nline2 modified\nline3';
    const { lastFrame } = render(
      <DiffDisplay oldContent={oldContent} newContent={newContent} mode="side-by-side" />
    );
    const frame = lastFrame();
    expect(frame).toContain('line1');
    expect(frame).toContain('line2');
    expect(frame).toContain('modified');
    expect(frame).toContain('│');
  });

  it('truncates large diffs', () => {
    const lines = Array.from({ length: 60 }, (_, i) => `line ${i}`).join('\n');
    const newLines = lines + '\nadded line';
    const { lastFrame } = render(
      <DiffDisplay oldContent={lines} newContent={newLines} />
    );
    const frame = lastFrame();
    expect(frame).toContain('line 0');
    expect(frame).toContain('line 19');
    expect(frame).toContain('more lines');
    expect(frame).toContain('line 59');
    expect(frame).not.toContain('line 30');
  });

  it('handles binary files', () => {
    const { lastFrame } = render(
      <DiffDisplay oldContent={`foo${String.fromCharCode(0)}bar`} newContent={`foo${String.fromCharCode(0)}baz`} />
    );
    expect(lastFrame()).toContain('Binary file changed');
  });

  it('renders additions only', () => {
    const { lastFrame } = render(
      <DiffDisplay oldContent="" newContent="line1" />
    );
    expect(lastFrame()).toContain('+ line1');
  });

  it('renders deletions only', () => {
    const { lastFrame } = render(
      <DiffDisplay oldContent="line1" newContent="" />
    );
    expect(lastFrame()).toContain('- line1');
  });

  it('renders DiffBar summary', () => {
      const { lastFrame } = render(
      <DiffDisplay oldContent="" newContent="a" />
    );
    expect(lastFrame()).toContain('+1');
    expect(lastFrame()).toContain('-0');
  });

  it('handles empty input gracefully', () => {
     const { lastFrame } = render(
      <DiffDisplay oldContent="" newContent="" />
    );
    expect(lastFrame()).toContain('No changes');
  });

   it('aligns side-by-side modification blocks', () => {
    const oldContent = 'A';
    const newContent = 'B';
    const { lastFrame } = render(
      <DiffDisplay oldContent={oldContent} newContent={newContent} mode="side-by-side" />
    );
    const frame = lastFrame();
    expect(frame).toContain('A');
    expect(frame).toContain('B');
  });

  it('renders context lines in gray/dim', () => {
     const { lastFrame } = render(
      <DiffDisplay oldContent="context" newContent="context" />
    );
    expect(lastFrame()).toContain('context');
  });

  it('handles mixed changes', () => {
      const oldContent = '1\n2\n3';
      const newContent = '1\n2a\n3';
      const { lastFrame } = render(
        <DiffDisplay oldContent={oldContent} newContent={newContent} />
      );
      expect(lastFrame()).toContain('1');
      expect(lastFrame()).toContain('- 2');
      expect(lastFrame()).toContain('+ 2a');
      expect(lastFrame()).toContain('3');
  });

  it('defaults to inline mode', () => {
       const { lastFrame } = render(
        <DiffDisplay oldContent="a" newContent="b" />
      );
      expect(lastFrame()).not.toContain('│');
  });
});

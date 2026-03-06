import React, { useMemo } from 'react';
import { Box, Text, useStdout } from 'ink';
import { diffLines } from 'diff';
import { highlight } from 'cli-highlight';
import { DiffBar } from './DiffBar.js';

const safeHighlight = (code: string, language?: string): string => {
  if (!code || !language) return code;
  try {
    return highlight(code, { language, ignoreIllegals: true });
  } catch {
    return code;
  }
};

export interface DiffDisplayProps {
  oldContent?: string;
  newContent?: string;
  diff?: string;
  language?: string;
  mode?: 'inline' | 'side-by-side';
}

interface DiffLineData {
  type: 'add' | 'remove' | 'context' | 'empty';
  content: string;
  index?: number;
}

const TRUNCATE_THRESHOLD = 50;
const HEAD_LINES = 20;
const TAIL_LINES = 10;

const DiffDisplayComponent: React.FC<DiffDisplayProps> = ({
  oldContent = '',
  newContent = '',
  language = 'javascript',
  mode = 'inline',
}) => {
  const { stdout } = useStdout();
  const width = stdout?.columns ?? 80;
  const effectiveMode = mode === 'side-by-side' || (mode === 'inline' && width >= 120) ? 'side-by-side' : 'inline';

  const isBinary = useMemo(() => {
    return oldContent.includes('\0') || newContent.includes('\0');
  }, [oldContent, newContent]);

  const { lines, additions, deletions, truncated } = useMemo(() => {
    if (isBinary) {
      return { lines: [], additions: 0, deletions: 0, truncated: false };
    }

    const changes = diffLines(oldContent, newContent);
    let addCount = 0;
    let delCount = 0;
    const allLines: DiffLineData[] = [];

    changes.forEach((change) => {
      const changeLines = change.value.split('\n');
      if (changeLines[changeLines.length - 1] === '') {
        changeLines.pop();
      }

      if (change.added) {
        addCount += changeLines.length;
        changeLines.forEach((line) => allLines.push({ type: 'add', content: line }));
      } else if (change.removed) {
        delCount += changeLines.length;
        changeLines.forEach((line) => allLines.push({ type: 'remove', content: line }));
      } else {
        changeLines.forEach((line) => allLines.push({ type: 'context', content: line }));
      }
    });

    let displayLines = allLines;
    let isTruncated = false;
    if (allLines.length > TRUNCATE_THRESHOLD) {
      isTruncated = true;
      const head = allLines.slice(0, HEAD_LINES);
      const tail = allLines.slice(allLines.length - TAIL_LINES);
      displayLines = [...head, { type: 'context', content: `... ${allLines.length - HEAD_LINES - TAIL_LINES} more lines ...` }, ...tail];
    }

    return { lines: displayLines, additions: addCount, deletions: delCount, truncated: isTruncated };
  }, [oldContent, newContent, isBinary]);

  if (isBinary) {
    return (
      <Box flexDirection="column">
        <Text color="yellow">Binary file changed</Text>
        <DiffBar additions={0} deletions={0} />
      </Box>
    );
  }

  const sideBySideRows = useMemo(() => {
    if (effectiveMode !== 'side-by-side') return [];

    const rows: { left: DiffLineData; right: DiffLineData }[] = [];
    let i = 0;
    while (i < lines.length) {
      const current = lines[i];
      if (!current) break;

      if (current.type === 'context') {
        rows.push({ left: current, right: current });
        i++;
      } else if (current.type === 'remove') {
        let j = i;
        const removes: DiffLineData[] = [];
        while (j < lines.length && lines[j]?.type === 'remove') {
          removes.push(lines[j]!);
          j++;
        }

        const adds: DiffLineData[] = [];
        while (j < lines.length && lines[j]?.type === 'add') {
          adds.push(lines[j]!);
          j++;
        }

        const maxLen = Math.max(removes.length, adds.length);
        for (let k = 0; k < maxLen; k++) {
          rows.push({
            left: removes[k] || { type: 'empty', content: '' },
            right: adds[k] || { type: 'empty', content: '' },
          });
        }
        i = j;
      } else if (current.type === 'add') {
         rows.push({
          left: { type: 'empty', content: '' },
          right: current,
        });
        i++;
      }
    }
    return rows;
  }, [lines, effectiveMode]);


  const renderInline = () => (
    <Box flexDirection="column">
      {lines.map((line, idx) => (
        <Box key={idx} flexDirection="row">
          <Text color="gray" dimColor>{(idx + 1).toString().padStart(4, ' ')} </Text>
          {line.type === 'context' && <Text dimColor>{safeHighlight(line.content, language)}</Text>}
          {line.type === 'add' && <Text color="green">+ {safeHighlight(line.content, language)}</Text>}
          {line.type === 'remove' && <Text color="red">- {safeHighlight(line.content, language)}</Text>}
        </Box>
      ))}
    </Box>
  );

  const renderSideBySide = () => {
    const halfWidth = Math.floor((width - 6) / 2);

    return (
      <Box flexDirection="column">
        {sideBySideRows.map((row, idx) => (
          <Box key={idx} flexDirection="row">
            <Box width={halfWidth} flexDirection="row">
              {row.left.type !== 'empty' && (
                <>
                  <Text color="gray" dimColor>{(idx + 1).toString().padStart(4, ' ')} </Text>
                  <Box width={halfWidth - 5}>
                     {row.left.type === 'context' && <Text dimColor wrap="truncate-end">{safeHighlight(row.left.content, language)}</Text>}
                     {row.left.type === 'remove' && <Text color="red" wrap="truncate-end">- {safeHighlight(row.left.content, language)}</Text>}
                  </Box>
                </>
              )}
            </Box>

            <Box width={2}><Text color="gray">│</Text></Box>

             <Box width={halfWidth} flexDirection="row">
              {row.right.type !== 'empty' && (
                 <>
                   {row.right.type === 'context' && <Text dimColor wrap="truncate-end">{safeHighlight(row.right.content, language)}</Text>}
                   {row.right.type === 'add' && <Text color="green" wrap="truncate-end">+ {safeHighlight(row.right.content, language)}</Text>}
                 </>
              )}
            </Box>
          </Box>
        ))}
      </Box>
    );
  };

  return (
    <Box flexDirection="column" gap={1}>
       <DiffBar additions={additions} deletions={deletions} width={Math.min(width - 20, 60)} />
       {effectiveMode === 'inline' ? renderInline() : renderSideBySide()}
       {truncated && <Text color="yellow" dimColor>... {additions + deletions} lines modified ...</Text>}
    </Box>
  );
};

export const DiffDisplay = React.memo(DiffDisplayComponent);

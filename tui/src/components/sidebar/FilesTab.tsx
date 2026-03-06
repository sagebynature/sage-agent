import React, { useMemo } from "react";
import { Box, Text } from "ink";
import { useApp } from "../../state/AppContext.js";
import { COLORS } from "../../theme/colors.js";

const FILE_TOOLS = ["file_read", "file_write", "file_edit"];

interface FileStats {
  path: string;
  reads: number;
  writes: number;
  edits: number;
}

const getPath = (args: Record<string, unknown>): string | null => {
  if (typeof args.path === "string") return args.path;
  if (typeof args.file_path === "string") return args.file_path;
  return null;
};

export const FilesTab: React.FC = () => {
  const { state } = useApp();
  const { tools } = state;

  const files = useMemo(() => {
    const stats = new Map<string, FileStats>();

    tools.forEach((tool) => {
      if (!FILE_TOOLS.includes(tool.name)) return;

      const path = getPath(tool.arguments);
      if (!path) return;

      const relativePath = path.startsWith(process.cwd())
        ? path.slice(process.cwd().length + 1)
        : path;

      if (!stats.has(relativePath)) {
        stats.set(relativePath, { path: relativePath, reads: 0, writes: 0, edits: 0 });
      }

      const fileStat = stats.get(relativePath)!;

      if (tool.name === "file_read") fileStat.reads++;
      else if (tool.name === "file_write") fileStat.writes++;
      else if (tool.name === "file_edit") fileStat.edits++;
    });

    return Array.from(stats.values()).sort((a, b) => a.path.localeCompare(b.path));
  }, [tools]);

  if (files.length === 0) {
    return (
      <Box padding={1}>
        <Text color={COLORS.dimmed}>No files touched</Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column" gap={1} padding={1}>
      <Text color={COLORS.dimmed}>Modified Files</Text>
      {files.map((file) => (
        <Box key={file.path} flexDirection="column" borderStyle="single" borderColor={COLORS.dimmed} paddingX={1}>
          <Text color={COLORS.accent} wrap="truncate-middle">{file.path}</Text>
          <Box gap={2} marginTop={0}>
            {file.reads > 0 && <Text color={COLORS.dimmed}>R: {file.reads}</Text>}
            {file.writes > 0 && <Text color={COLORS.dimmed}>W: {file.writes}</Text>}
            {file.edits > 0 && <Text color={COLORS.dimmed}>E: {file.edits}</Text>}
          </Box>
        </Box>
      ))}
    </Box>
  );
};

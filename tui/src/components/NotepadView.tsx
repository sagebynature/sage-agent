import { Box, Text } from "ink";

interface NotepadViewProps {
  content: string;
}

export function NotepadView({ content }: NotepadViewProps) {
  if (!content) {
    return (
      <Box borderStyle="round" borderColor="dim" padding={1}>
        <Text color="dim">No notes yet</Text>
      </Box>
    );
  }

  return (
    <Box borderStyle="round" borderColor="gray" padding={1} flexDirection="column">
      <Text>{content}</Text>
    </Box>
  );
}

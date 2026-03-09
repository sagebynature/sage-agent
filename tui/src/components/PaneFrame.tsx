import { Box, Text } from "ink";
import { memo, type ReactNode } from "react";

interface PaneFrameProps {
  title: string;
  width: number;
  height?: number;
  flexGrow?: number;
  flexShrink?: number;
  children: ReactNode;
}

function topBorder(title: string, width: number): string {
  const safeWidth = Math.max(width, title.length + 4);
  const innerWidth = safeWidth - 2;
  const titleText = ` ${title} `;
  return `╭${titleText}${"─".repeat(Math.max(0, innerWidth - titleText.length))}╮`;
}

function bottomBorder(width: number): string {
  const safeWidth = Math.max(width, 4);
  return `╰${"─".repeat(safeWidth - 2)}╯`;
}

export const PaneFrame = memo(function PaneFrame({
  title,
  width,
  height,
  flexGrow,
  flexShrink,
  children,
}: PaneFrameProps): ReactNode {
  const safeWidth = Math.max(width, title.length + 4);
  const bodyHeight = height ? Math.max(1, height - 2) : undefined;

  return (
    <Box
      width={safeWidth}
      height={height}
      flexGrow={flexGrow}
      flexShrink={flexShrink}
      flexDirection="column"
    >
      <Text color="gray">{topBorder(title, safeWidth)}</Text>
      <Box
        width={safeWidth}
        flexDirection="column"
        borderStyle="round"
        borderTop={false}
        borderBottom={false}
        borderColor="gray"
        paddingX={1}
        {...(bodyHeight ? { height: bodyHeight, overflowY: "hidden" as const } : {})}
      >
        {children}
      </Box>
      <Text color="gray">{bottomBorder(safeWidth)}</Text>
    </Box>
  );
});

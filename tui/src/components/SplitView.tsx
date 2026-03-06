import React, { useState, useEffect, type ReactNode } from "react";
import { Box, Text, useInput, useStdout } from "ink";
import { AgentTab } from "./sidebar/AgentTab.js";
import { UsageTab } from "./sidebar/UsageTab.js";
import { FilesTab } from "./sidebar/FilesTab.js";
import { TasksTab } from "./sidebar/TasksTab.js";
import { COLORS } from "../theme/colors.js";
import { useApp } from "../state/AppContext.js";

type Tab = "Agent" | "Usage" | "Files" | "Tasks";
const TABS: Tab[] = ["Agent", "Usage", "Files", "Tasks"];

interface SplitViewProps {
  children: ReactNode;
}

export const SplitView: React.FC<SplitViewProps> = ({ children }) => {
  const { state } = useApp();
  const { stdout } = useStdout();
  const [sidebarWidthPercent, setSidebarWidthPercent] = useState(30);
  const [activeTabIndex, setActiveTabIndex] = useState(0);
  const [isSidebarVisible, setIsSidebarVisible] = useState(true);
  // Handle terminal resize
  useEffect(() => {
    if (!stdout) return;

    // Initial check
    if (stdout.columns < 100) {
      setIsSidebarVisible(false);
    }

    const onResize = () => {
      if (stdout.columns < 100) {
        setIsSidebarVisible(false);
      } else {
        setIsSidebarVisible(true);
      }
    };

    stdout.on("resize", onResize);
    return () => {
      stdout.off("resize", onResize);
    };
  }, [stdout]);

  useInput((input, key) => {
    // Tab cycling
    if (key.tab) {
      setActiveTabIndex((prev) => (prev + 1) % TABS.length);
    }

    // Toggle sidebar
    if (input === "\x02" || (key.ctrl && input === "b")) { // Ctrl+B
      setIsSidebarVisible((prev) => !prev);
    }

    // Resize sidebar
    if (input === "\x1b") { // Escape sequence start
       // Ink handles ctrl keys specifically usually, let's check key modifier
    }

    // Ctrl+[ is often mapped to Escape in terminals, but if we want strictly Ctrl+[
    // ink provides key.ctrl and input '['? No.
    // Ctrl+[ sends Escape (0x1b).
    // Ctrl+] sends 0x1d (Group Separator).

    // Let's rely on checking input string for these control characters
    // Ctrl+[ is \x1b (Escape)
    // Ctrl+] is \x1d

    if (input === "\x1b") { // Ctrl+[
      setSidebarWidthPercent((prev) => Math.max(20, prev - 5));
    }

    if (input === "\x1d") { // Ctrl+]
      setSidebarWidthPercent((prev) => Math.min(50, prev + 5));
    }
  });

  const activeTab = TABS[activeTabIndex];

  // Counts for badges
  const getBadgeCount = (tab: Tab): number | null => {
    switch (tab) {
      case "Files": {
        // Simple heuristic: count distinct file paths in tools
        const paths = new Set();
        state.tools.forEach(t => {
           if (t.name.startsWith("file_") && (t.arguments.path || t.arguments.file_path)) {
             paths.add(t.arguments.path || t.arguments.file_path);
           }
        });
        return paths.size || null;
      }
      case "Agent":
        return state.agents.length || null;
      default:
        return null;
    }
  };

  const renderSidebarContent = () => {
    switch (activeTab) {
      case "Agent": return <AgentTab />;
      case "Usage": return <UsageTab />;
      case "Files": return <FilesTab />;
      case "Tasks": return <TasksTab />;
      default: return null;
    }
  };

  return (
    <Box flexDirection="row" width="100%" height="100%">
      {/* Main Content Panel */}
      <Box
        flexGrow={1}
        flexShrink={1}
        width={isSidebarVisible ? `${100 - sidebarWidthPercent}%` : "100%"}
        borderColor={COLORS.dimmed}
        borderStyle="single"
        padding={1}
      >
        {children}
      </Box>

      {/* Sidebar Panel */}
      {isSidebarVisible && (
        <Box
          flexDirection="column"
          width={`${sidebarWidthPercent}%`}
          flexShrink={0}
          borderStyle="single"
          borderColor={COLORS.dimmed}
          borderLeft={false}
        >
          {/* Tabs Header */}
          <Box borderStyle="single" borderTop={false} borderLeft={false} borderRight={false} borderColor={COLORS.dimmed} paddingX={1}>
             {TABS.map((tab, index) => {
               const isActive = index === activeTabIndex;
               const count = getBadgeCount(tab);

               return (
                 <Box key={tab} marginRight={2}>
                   <Text
                     color={isActive ? COLORS.accent : COLORS.dimmed}
                     bold={isActive}
                     backgroundColor={isActive ? undefined : undefined} // ink doesn't support bg color on Text easily without Box
                   >
                     {tab}
                     {count !== null && <Text color={COLORS.dimmed}> ({count})</Text>}
                   </Text>
                 </Box>
               );
             })}
          </Box>

          {/* Tab Content */}
          <Box flexGrow={1} flexDirection="column">
            {renderSidebarContent()}
          </Box>

          {/* Footer / Shortcuts hint */}
          <Box borderStyle="single" borderBottom={false} borderLeft={false} borderRight={false} borderColor={COLORS.dimmed} paddingX={1}>
             <Text color={COLORS.dimmed} dimColor>
               Tab:Cycle | Ctrl+B:Toggle | Ctrl+[/]:Resize
             </Text>
          </Box>
        </Box>
      )}
    </Box>
  );
};

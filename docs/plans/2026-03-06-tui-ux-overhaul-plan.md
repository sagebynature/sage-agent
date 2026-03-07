# TUI UX Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite the TUI view layer to use Ink's `<Static>` for native terminal scrolling, render markdown in agent output, show tool calls inline, and adopt Claude Code-style minimal chrome.

**Architecture:** Split into Static zone (completed blocks written once to terminal scroll buffer via `<Static>`) and Dynamic zone (active stream + input + status bar). The integration layer (EventRouter, wiring, SageClient) stays unchanged — only the state model, reducer, and view components change.

**Tech Stack:** TypeScript, React 19, Ink 6, marked + marked-terminal, cli-highlight, vitest

**Test commands:**
- `cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run`
- `cd /Users/sachoi/sagebynature/sage-agent/tui && npx tsc --noEmit`

---

### Task 1: New state types — OutputBlock, ActiveStream, revised AppState

**Files:**
- Create: `tui/src/types/blocks.ts`
- Modify: `tui/src/types/state.ts`

**Step 1: Create block types**

Create `tui/src/types/blocks.ts`:

```typescript
export interface ToolSummary {
  name: string;
  callId: string;
  arguments: Record<string, unknown>;
  result?: string;
  error?: string;
  durationMs?: number;
  status: "running" | "completed" | "failed";
}

export interface OutputBlock {
  id: string;
  type: "user" | "text" | "tool" | "error" | "system";
  content: string;
  tools?: ToolSummary[];
  timestamp: number;
}

export interface ActiveStream {
  runId: string;
  content: string;
  tools: ToolSummary[];
  isThinking: boolean;
  startedAt: number;
}
```

**Step 2: Add new state shape to state.ts**

In `tui/src/types/state.ts`, add after the existing `AppState` interface (keep old types for now — we'll remove them in Task 7):

```typescript
import type { OutputBlock, ActiveStream } from "./blocks.js";

export interface AppStateV2 {
  completedBlocks: OutputBlock[];
  activeStream: ActiveStream | null;
  usage: UsageState;
  permissions: PermissionState[];
  error: string | null;
  session: SessionState | null;
}
```

**Step 3: Verify types compile**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx tsc --noEmit`

Expected: No new errors.

**Step 4: Commit**

```bash
git add tui/src/types/blocks.ts tui/src/types/state.ts
git commit -m "feat(tui): add OutputBlock, ActiveStream, AppStateV2 types"
```

---

### Task 2: New reducer — blockReducer with OutputBlock/ActiveStream actions

**Files:**
- Create: `tui/src/state/blockReducer.ts`
- Create: `tui/src/state/__tests__/blockReducer.test.ts`

**Step 1: Write failing tests**

Create `tui/src/state/__tests__/blockReducer.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { blockReducer, INITIAL_BLOCK_STATE } from "../blockReducer.js";
import type { BlockAction } from "../blockReducer.js";

describe("blockReducer", () => {
  it("SUBMIT_MESSAGE appends user block to completedBlocks", () => {
    const state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "SUBMIT_MESSAGE",
      content: "hello world",
    });
    expect(state.completedBlocks).toHaveLength(1);
    expect(state.completedBlocks[0]!.type).toBe("user");
    expect(state.completedBlocks[0]!.content).toBe("hello world");
  });

  it("STREAM_START creates activeStream with isThinking true", () => {
    const state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    expect(state.activeStream).not.toBeNull();
    expect(state.activeStream!.runId).toBe("run-1");
    expect(state.activeStream!.isThinking).toBe(true);
    expect(state.activeStream!.content).toBe("");
  });

  it("STREAM_DELTA appends to activeStream content and clears isThinking", () => {
    const started = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    const state = blockReducer(started, {
      type: "STREAM_DELTA",
      delta: "hello ",
    });
    expect(state.activeStream!.content).toBe("hello ");
    expect(state.activeStream!.isThinking).toBe(false);

    const state2 = blockReducer(state, {
      type: "STREAM_DELTA",
      delta: "world",
    });
    expect(state2.activeStream!.content).toBe("hello world");
  });

  it("STREAM_DELTA is no-op when no activeStream", () => {
    const state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_DELTA",
      delta: "orphan",
    });
    expect(state).toBe(INITIAL_BLOCK_STATE);
  });

  it("TOOL_STARTED adds running tool to activeStream", () => {
    const started = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    const state = blockReducer(started, {
      type: "TOOL_STARTED",
      name: "shell",
      callId: "call-1",
      arguments: { command: "ls" },
    });
    expect(state.activeStream!.tools).toHaveLength(1);
    expect(state.activeStream!.tools[0]!.status).toBe("running");
    expect(state.activeStream!.tools[0]!.name).toBe("shell");
  });

  it("TOOL_COMPLETED updates tool status in activeStream", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    state = blockReducer(state, {
      type: "TOOL_STARTED",
      name: "shell",
      callId: "call-1",
      arguments: { command: "ls" },
    });
    state = blockReducer(state, {
      type: "TOOL_COMPLETED",
      callId: "call-1",
      result: "file.txt",
      durationMs: 150,
    });
    expect(state.activeStream!.tools[0]!.status).toBe("completed");
    expect(state.activeStream!.tools[0]!.result).toBe("file.txt");
    expect(state.activeStream!.tools[0]!.durationMs).toBe(150);
  });

  it("STREAM_END flattens activeStream into completedBlocks", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    state = blockReducer(state, {
      type: "TOOL_STARTED",
      name: "read",
      callId: "call-1",
      arguments: { path: "file.txt" },
    });
    state = blockReducer(state, {
      type: "TOOL_COMPLETED",
      callId: "call-1",
      result: "contents",
      durationMs: 50,
    });
    state = blockReducer(state, {
      type: "STREAM_DELTA",
      delta: "Here is the file.",
    });
    state = blockReducer(state, { type: "STREAM_END", status: "success" });

    expect(state.activeStream).toBeNull();
    // Should have tool block + text block
    expect(state.completedBlocks.length).toBeGreaterThanOrEqual(2);
    const types = state.completedBlocks.map((b) => b.type);
    expect(types).toContain("tool");
    expect(types).toContain("text");
  });

  it("STREAM_END with error appends error block", () => {
    let state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "STREAM_START",
      runId: "run-1",
    });
    state = blockReducer(state, {
      type: "STREAM_END",
      status: "error",
      error: "model exploded",
    });
    expect(state.activeStream).toBeNull();
    const errorBlocks = state.completedBlocks.filter((b) => b.type === "error");
    expect(errorBlocks).toHaveLength(1);
    expect(errorBlocks[0]!.content).toContain("model exploded");
  });

  it("UPDATE_USAGE updates usage state", () => {
    const state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "UPDATE_USAGE",
      usage: { model: "gpt-4", promptTokens: 100 },
    });
    expect(state.usage.model).toBe("gpt-4");
    expect(state.usage.promptTokens).toBe(100);
  });

  it("SET_ERROR and CLEAR_ERROR manage error state", () => {
    const s1 = blockReducer(INITIAL_BLOCK_STATE, {
      type: "SET_ERROR",
      error: "oops",
    });
    expect(s1.error).toBe("oops");
    const s2 = blockReducer(s1, { type: "CLEAR_ERROR" });
    expect(s2.error).toBeNull();
  });

  it("PERMISSION_REQUEST and PERMISSION_RESPOND manage permissions", () => {
    const s1 = blockReducer(INITIAL_BLOCK_STATE, {
      type: "PERMISSION_REQUEST",
      permission: {
        id: "p1",
        tool: "shell",
        arguments: { command: "rm" },
        riskLevel: "high",
        status: "pending",
      },
    });
    expect(s1.permissions).toHaveLength(1);
    const s2 = blockReducer(s1, {
      type: "PERMISSION_RESPOND",
      id: "p1",
      decision: "allow_once",
    });
    expect(s2.permissions[0]!.status).toBe("approved");
  });

  it("ADD_SYSTEM_BLOCK appends system block", () => {
    const state = blockReducer(INITIAL_BLOCK_STATE, {
      type: "ADD_SYSTEM_BLOCK",
      content: "Context compaction started",
    });
    expect(state.completedBlocks).toHaveLength(1);
    expect(state.completedBlocks[0]!.type).toBe("system");
  });
});
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run src/state/__tests__/blockReducer.test.ts`

Expected: FAIL — module not found.

**Step 3: Implement blockReducer**

Create `tui/src/state/blockReducer.ts`:

```typescript
import type { OutputBlock, ActiveStream, ToolSummary } from "../types/blocks.js";
import type {
  UsageState,
  PermissionState,
  PermissionDecision,
  SessionState,
} from "../types/state.js";

export interface BlockState {
  completedBlocks: OutputBlock[];
  activeStream: ActiveStream | null;
  usage: UsageState;
  permissions: PermissionState[];
  error: string | null;
  session: SessionState | null;
}

export type BlockAction =
  | { type: "SUBMIT_MESSAGE"; content: string }
  | { type: "STREAM_START"; runId: string }
  | { type: "STREAM_DELTA"; delta: string }
  | { type: "TOOL_STARTED"; name: string; callId: string; arguments: Record<string, unknown> }
  | { type: "TOOL_COMPLETED"; callId: string; result?: string; error?: string; durationMs?: number }
  | { type: "STREAM_END"; status: "success" | "error" | "cancelled"; error?: string }
  | { type: "UPDATE_USAGE"; usage: Partial<UsageState> }
  | { type: "SET_ERROR"; error: string }
  | { type: "CLEAR_ERROR" }
  | { type: "PERMISSION_REQUEST"; permission: PermissionState }
  | { type: "PERMISSION_RESPOND"; id: string; decision: PermissionDecision }
  | { type: "SET_SESSION"; session: SessionState | null }
  | { type: "ADD_SYSTEM_BLOCK"; content: string };

export const INITIAL_BLOCK_STATE: BlockState = {
  completedBlocks: [],
  activeStream: null,
  usage: {
    promptTokens: 0,
    completionTokens: 0,
    totalCost: 0,
    model: "",
    contextUsagePercent: 0,
  },
  permissions: [],
  error: null,
  session: null,
};

function makeId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function resolvePermissionStatus(
  decision: PermissionDecision,
): "approved" | "denied" {
  if (decision === "deny") return "denied";
  return "approved";
}

function flattenStream(stream: ActiveStream): OutputBlock[] {
  const blocks: OutputBlock[] = [];
  const now = Date.now();

  // Emit tool blocks for completed tools
  for (const tool of stream.tools) {
    blocks.push({
      id: makeId("tool"),
      type: "tool",
      content: tool.name,
      tools: [tool],
      timestamp: now,
    });
  }

  // Emit text block if there's content
  const text = stream.content.trim();
  if (text.length > 0) {
    blocks.push({
      id: makeId("text"),
      type: "text",
      content: text,
      timestamp: now,
    });
  }

  return blocks;
}

export function blockReducer(state: BlockState, action: BlockAction): BlockState {
  switch (action.type) {
    case "SUBMIT_MESSAGE":
      return {
        ...state,
        completedBlocks: [
          ...state.completedBlocks,
          {
            id: makeId("user"),
            type: "user",
            content: action.content,
            timestamp: Date.now(),
          },
        ],
      };

    case "STREAM_START":
      return {
        ...state,
        activeStream: {
          runId: action.runId,
          content: "",
          tools: [],
          isThinking: true,
          startedAt: Date.now(),
        },
      };

    case "STREAM_DELTA": {
      if (!state.activeStream) return state;
      return {
        ...state,
        activeStream: {
          ...state.activeStream,
          content: state.activeStream.content + action.delta,
          isThinking: false,
        },
      };
    }

    case "TOOL_STARTED": {
      if (!state.activeStream) return state;
      const newTool: ToolSummary = {
        name: action.name,
        callId: action.callId,
        arguments: action.arguments,
        status: "running",
      };
      return {
        ...state,
        activeStream: {
          ...state.activeStream,
          tools: [...state.activeStream.tools, newTool],
        },
      };
    }

    case "TOOL_COMPLETED": {
      if (!state.activeStream) return state;
      return {
        ...state,
        activeStream: {
          ...state.activeStream,
          tools: state.activeStream.tools.map((t) =>
            t.callId === action.callId
              ? {
                  ...t,
                  status: (action.error ? "failed" : "completed") as ToolSummary["status"],
                  result: action.result,
                  error: action.error,
                  durationMs: action.durationMs,
                }
              : t,
          ),
        },
      };
    }

    case "STREAM_END": {
      const blocks: OutputBlock[] = [];

      if (state.activeStream) {
        blocks.push(...flattenStream(state.activeStream));
      }

      if (action.status === "error" && action.error) {
        blocks.push({
          id: makeId("error"),
          type: "error",
          content: action.error,
          timestamp: Date.now(),
        });
      }

      return {
        ...state,
        completedBlocks: [...state.completedBlocks, ...blocks],
        activeStream: null,
      };
    }

    case "UPDATE_USAGE":
      return { ...state, usage: { ...state.usage, ...action.usage } };

    case "SET_ERROR":
      return { ...state, error: action.error };

    case "CLEAR_ERROR":
      return { ...state, error: null };

    case "PERMISSION_REQUEST":
      return {
        ...state,
        permissions: [...state.permissions, action.permission],
      };

    case "PERMISSION_RESPOND":
      return {
        ...state,
        permissions: state.permissions.map((p) =>
          p.id === action.id
            ? { ...p, status: resolvePermissionStatus(action.decision) }
            : p,
        ),
      };

    case "SET_SESSION":
      return { ...state, session: action.session };

    case "ADD_SYSTEM_BLOCK":
      return {
        ...state,
        completedBlocks: [
          ...state.completedBlocks,
          {
            id: makeId("system"),
            type: "system",
            content: action.content,
            timestamp: Date.now(),
          },
        ],
      };

    default:
      return state;
  }
}
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run src/state/__tests__/blockReducer.test.ts`

Expected: ALL PASS.

**Step 5: Commit**

```bash
git add tui/src/types/blocks.ts tui/src/types/state.ts tui/src/state/blockReducer.ts tui/src/state/__tests__/blockReducer.test.ts
git commit -m "feat(tui): add blockReducer with OutputBlock/ActiveStream state model"
```

---

### Task 3: Block renderers — UserBlock, TextBlock, ToolBlock, StaticBlock

**Files:**
- Create: `tui/src/components/blocks/UserBlock.tsx`
- Create: `tui/src/components/blocks/TextBlock.tsx`
- Create: `tui/src/components/blocks/ToolBlock.tsx`
- Create: `tui/src/components/blocks/StaticBlock.tsx`
- Create: `tui/src/components/blocks/__tests__/blocks.test.tsx`

**Step 1: Create UserBlock**

Create `tui/src/components/blocks/UserBlock.tsx`:

```tsx
import { Box, Text } from "ink";
import type { ReactNode } from "react";

interface UserBlockProps {
  content: string;
}

export function UserBlock({ content }: UserBlockProps): ReactNode {
  return (
    <Box>
      <Text dimColor>{"> "}{content}</Text>
    </Box>
  );
}
```

**Step 2: Create TextBlock**

Create `tui/src/components/blocks/TextBlock.tsx`:

```tsx
import { Box, Text } from "ink";
import type { ReactNode } from "react";
import { renderMarkdown } from "../../renderer/MarkdownRenderer.js";

interface TextBlockProps {
  content: string;
}

export function TextBlock({ content }: TextBlockProps): ReactNode {
  const rendered = renderMarkdown(content, false);
  return (
    <Box flexDirection="column">
      <Text>{"● "}{rendered}</Text>
    </Box>
  );
}
```

**Step 3: Create ToolBlock**

Create `tui/src/components/blocks/ToolBlock.tsx`:

```tsx
import { Box, Text } from "ink";
import type { ReactNode } from "react";
import type { ToolSummary } from "../../types/blocks.js";

interface ToolBlockProps {
  name: string;
  tools: ToolSummary[];
}

function formatDuration(ms?: number): string {
  if (ms === undefined) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function toolStatusSuffix(tool: ToolSummary): string {
  if (tool.status === "running") return "... running";
  if (tool.status === "failed") return `✗ ${tool.error ?? "failed"}`;
  return formatDuration(tool.durationMs);
}

function toolSummaryLine(tools: ToolSummary[]): string {
  if (tools.length === 0) return "";
  if (tools.length === 1) {
    const t = tools[0]!;
    const suffix = toolStatusSuffix(t);
    const args = formatToolArgs(t);
    return `${t.name}${args}${suffix ? `  ${suffix}` : ""}`;
  }
  const name = tools[0]!.name;
  const allSame = tools.every((t) => t.name === name);
  if (allSame) {
    return `${name} (${tools.length} calls)`;
  }
  return `${tools.length} tool calls`;
}

function formatToolArgs(tool: ToolSummary): string {
  const args = tool.arguments;
  if (args.path) return ` ${args.path}`;
  if (args.file_path) return ` ${args.file_path}`;
  if (args.command) return ` ${args.command}`;
  return "";
}

export function ToolBlock({ name, tools }: ToolBlockProps): ReactNode {
  const summary = toolSummaryLine(tools);
  const subItems = tools.length > 1 ? tools : [];

  return (
    <Box flexDirection="column">
      <Text>{"● "}{summary}</Text>
      {subItems.map((tool) => (
        <Text key={tool.callId} dimColor>
          {"  ⎿  "}{tool.name}{formatToolArgs(tool)}
          {"  "}{toolStatusSuffix(tool)}
        </Text>
      ))}
    </Box>
  );
}
```

**Step 4: Create StaticBlock dispatcher**

Create `tui/src/components/blocks/StaticBlock.tsx`:

```tsx
import { Box, Text } from "ink";
import type { ReactNode } from "react";
import type { OutputBlock } from "../../types/blocks.js";
import { UserBlock } from "./UserBlock.js";
import { TextBlock } from "./TextBlock.js";
import { ToolBlock } from "./ToolBlock.js";

interface StaticBlockProps {
  block: OutputBlock;
}

export function StaticBlock({ block }: StaticBlockProps): ReactNode {
  switch (block.type) {
    case "user":
      return <UserBlock content={block.content} />;
    case "text":
      return <TextBlock content={block.content} />;
    case "tool":
      return <ToolBlock name={block.content} tools={block.tools ?? []} />;
    case "error":
      return (
        <Box>
          <Text color="red">{"● "}{block.content}</Text>
        </Box>
      );
    case "system":
      return (
        <Box>
          <Text dimColor italic>{"● "}{block.content}</Text>
        </Box>
      );
    default:
      return null;
  }
}
```

**Step 5: Write tests**

Create `tui/src/components/blocks/__tests__/blocks.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render } from "ink-testing-library";
import React from "react";
import { StaticBlock } from "../StaticBlock.js";
import type { OutputBlock } from "../../../types/blocks.js";

describe("StaticBlock", () => {
  it("renders user block with dimmed > prefix", () => {
    const block: OutputBlock = {
      id: "u1",
      type: "user",
      content: "hello world",
      timestamp: 1000,
    };
    const { lastFrame } = render(<StaticBlock block={block} />);
    expect(lastFrame()).toContain(">");
    expect(lastFrame()).toContain("hello world");
  });

  it("renders text block with bullet and markdown", () => {
    const block: OutputBlock = {
      id: "t1",
      type: "text",
      content: "some **bold** text",
      timestamp: 1000,
    };
    const { lastFrame } = render(<StaticBlock block={block} />);
    expect(lastFrame()).toContain("●");
  });

  it("renders tool block with summary", () => {
    const block: OutputBlock = {
      id: "tool1",
      type: "tool",
      content: "Read",
      tools: [
        {
          name: "Read",
          callId: "c1",
          arguments: { path: "file.txt" },
          status: "completed",
          durationMs: 150,
        },
      ],
      timestamp: 1000,
    };
    const { lastFrame } = render(<StaticBlock block={block} />);
    expect(lastFrame()).toContain("●");
    expect(lastFrame()).toContain("Read");
  });

  it("renders error block in red", () => {
    const block: OutputBlock = {
      id: "e1",
      type: "error",
      content: "something broke",
      timestamp: 1000,
    };
    const { lastFrame } = render(<StaticBlock block={block} />);
    expect(lastFrame()).toContain("something broke");
  });

  it("renders system block dimmed", () => {
    const block: OutputBlock = {
      id: "s1",
      type: "system",
      content: "compaction started",
      timestamp: 1000,
    };
    const { lastFrame } = render(<StaticBlock block={block} />);
    expect(lastFrame()).toContain("compaction started");
  });
});
```

**Step 6: Run tests**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run src/components/blocks/__tests__/blocks.test.tsx`

Expected: ALL PASS.

**Step 7: Commit**

```bash
git add tui/src/components/blocks/
git commit -m "feat(tui): add block renderers — UserBlock, TextBlock, ToolBlock, StaticBlock"
```

---

### Task 4: ActiveStreamView — live streaming + thinking indicator

**Files:**
- Create: `tui/src/components/ActiveStreamView.tsx`
- Create: `tui/src/components/__tests__/ActiveStreamView.test.tsx`

**Step 1: Write tests**

Create `tui/src/components/__tests__/ActiveStreamView.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render } from "ink-testing-library";
import React from "react";
import { ActiveStreamView } from "../ActiveStreamView.js";
import type { ActiveStream } from "../../types/blocks.js";

describe("ActiveStreamView", () => {
  it("shows thinking indicator when isThinking", () => {
    const stream: ActiveStream = {
      runId: "r1",
      content: "",
      tools: [],
      isThinking: true,
      startedAt: Date.now(),
    };
    const { lastFrame } = render(<ActiveStreamView stream={stream} />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("Thinking");
  });

  it("renders streaming content with bullet prefix", () => {
    const stream: ActiveStream = {
      runId: "r1",
      content: "Hello world",
      tools: [],
      isThinking: false,
      startedAt: Date.now(),
    };
    const { lastFrame } = render(<ActiveStreamView stream={stream} />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("Hello world");
  });

  it("shows running tool", () => {
    const stream: ActiveStream = {
      runId: "r1",
      content: "",
      tools: [
        {
          name: "Read",
          callId: "c1",
          arguments: { path: "file.txt" },
          status: "running",
        },
      ],
      isThinking: false,
      startedAt: Date.now(),
    };
    const { lastFrame } = render(<ActiveStreamView stream={stream} />);
    const frame = lastFrame() ?? "";
    expect(frame).toContain("Read");
    expect(frame).toContain("running");
  });

  it("returns null when stream is null", () => {
    const { lastFrame } = render(<ActiveStreamView stream={null} />);
    expect(lastFrame()).toBe("");
  });
});
```

**Step 2: Implement ActiveStreamView**

Create `tui/src/components/ActiveStreamView.tsx`:

```tsx
import { Box, Text } from "ink";
import Spinner from "ink-spinner";
import type { ReactNode } from "react";
import type { ActiveStream } from "../types/blocks.js";
import { renderMarkdown } from "../renderer/MarkdownRenderer.js";

interface ActiveStreamViewProps {
  stream: ActiveStream | null;
}

function formatElapsed(startedAt: number): string {
  const elapsed = Math.floor((Date.now() - startedAt) / 1000);
  if (elapsed < 60) return `${elapsed}s`;
  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  return `${min}m ${sec}s`;
}

export function ActiveStreamView({ stream }: ActiveStreamViewProps): ReactNode {
  if (!stream) return null;

  const runningTools = stream.tools.filter((t) => t.status === "running");

  return (
    <Box flexDirection="column">
      {runningTools.map((tool) => (
        <Text key={tool.callId}>
          {"● "}{tool.name}
          {tool.arguments.path ? ` ${tool.arguments.path}` : ""}
          {tool.arguments.command ? ` ${tool.arguments.command}` : ""}
          <Text dimColor>{"  ... running"}</Text>
        </Text>
      ))}
      {stream.isThinking ? (
        <Box>
          <Text color="cyan">{"✻ "}</Text>
          <Spinner type="dots" />
          <Text color="cyan">{" Thinking..."}</Text>
          <Text dimColor>{" ("}{formatElapsed(stream.startedAt)}{")"}</Text>
        </Box>
      ) : stream.content.length > 0 ? (
        <Box flexDirection="column">
          <Text>{"● "}{renderMarkdown(stream.content, true)}</Text>
        </Box>
      ) : null}
    </Box>
  );
}
```

**Step 3: Run tests**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run src/components/__tests__/ActiveStreamView.test.tsx`

Expected: ALL PASS.

**Step 4: Commit**

```bash
git add tui/src/components/ActiveStreamView.tsx tui/src/components/__tests__/ActiveStreamView.test.tsx
git commit -m "feat(tui): add ActiveStreamView with thinking indicator and live markdown"
```

---

### Task 5: ConversationView — Static + ActiveStream

**Files:**
- Create: `tui/src/components/ConversationView.tsx`

**Step 1: Implement ConversationView**

Create `tui/src/components/ConversationView.tsx`:

```tsx
import { Box, Static, Text } from "ink";
import type { ReactNode } from "react";
import type { OutputBlock, ActiveStream } from "../types/blocks.js";
import { StaticBlock } from "./blocks/StaticBlock.js";
import { ActiveStreamView } from "./ActiveStreamView.js";

interface ConversationViewProps {
  completedBlocks: OutputBlock[];
  activeStream: ActiveStream | null;
}

export function ConversationView({
  completedBlocks,
  activeStream,
}: ConversationViewProps): ReactNode {
  return (
    <Box flexDirection="column">
      <Static items={completedBlocks}>
        {(block) => (
          <Box key={block.id} flexDirection="column">
            <StaticBlock block={block} />
          </Box>
        )}
      </Static>
      <ActiveStreamView stream={activeStream} />
    </Box>
  );
}
```

**Step 2: Verify types compile**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx tsc --noEmit`

Expected: No new errors.

**Step 3: Commit**

```bash
git add tui/src/components/ConversationView.tsx
git commit -m "feat(tui): add ConversationView with Static scroll + ActiveStreamView"
```

---

### Task 6: BottomBar + InputPrompt — minimal chrome

**Files:**
- Create: `tui/src/components/BottomBar.tsx`
- Create: `tui/src/components/InputPrompt.tsx`

**Step 1: Create BottomBar**

Create `tui/src/components/BottomBar.tsx`:

```tsx
import { Box, Text } from "ink";
import type { ReactNode } from "react";
import type { UsageState } from "../types/state.js";

interface BottomBarProps {
  usage: UsageState;
}

function contextBar(percent: number): string {
  const filled = Math.round(percent / 10);
  const empty = 10 - filled;
  return "█".repeat(filled) + "░".repeat(empty);
}

function contextColor(percent: number): string {
  if (percent >= 90) return "red";
  if (percent >= 70) return "yellow";
  return "green";
}

export function BottomBar({ usage }: BottomBarProps): ReactNode {
  const cost = usage.totalCost > 0 ? `$${usage.totalCost.toFixed(2)}` : "";
  const model = usage.model || "no model";
  const pct = usage.contextUsagePercent;

  return (
    <Box>
      <Text dimColor>
        {"  "}{model}
        {" | "}
        <Text color={contextColor(pct)}>{contextBar(pct)}</Text>
        {" "}{pct}%
        {cost ? ` | ${cost}` : ""}
      </Text>
    </Box>
  );
}
```

**Step 2: Create InputPrompt**

Create `tui/src/components/InputPrompt.tsx`:

```tsx
import { Box, Text } from "ink";
import TextInput from "ink-text-input";
import { type ReactNode, useState, useCallback } from "react";

interface InputPromptProps {
  onSubmit: (text: string) => void;
  isActive?: boolean;
}

function Divider(): ReactNode {
  return (
    <Box>
      <Text dimColor>{"─".repeat(80)}</Text>
    </Box>
  );
}

export function InputPrompt({ onSubmit, isActive = true }: InputPromptProps): ReactNode {
  const [value, setValue] = useState("");

  const handleSubmit = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      onSubmit(text);
      setValue("");
    },
    [onSubmit],
  );

  return (
    <Box flexDirection="column">
      <Divider />
      <Box>
        <Text color="cyan">{"> "}</Text>
        <TextInput
          value={value}
          onChange={setValue}
          onSubmit={handleSubmit}
          placeholder="Type your message..."
          focus={isActive}
        />
      </Box>
      <Divider />
    </Box>
  );
}
```

**Step 3: Verify types compile**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx tsc --noEmit`

Expected: No new errors.

**Step 4: Commit**

```bash
git add tui/src/components/BottomBar.tsx tui/src/components/InputPrompt.tsx
git commit -m "feat(tui): add BottomBar and InputPrompt with minimal chrome"
```

---

### Task 7: Wire into AppShell — new BlockProvider + EventRouter bridge

**Files:**
- Create: `tui/src/state/BlockContext.tsx`
- Create: `tui/src/integration/BlockEventRouter.ts`
- Modify: `tui/src/components/App.tsx`

**Step 1: Create BlockContext (provider + hook)**

Create `tui/src/state/BlockContext.tsx`:

```tsx
import { createContext, use, useReducer, type ReactNode } from "react";
import { blockReducer, INITIAL_BLOCK_STATE, type BlockState, type BlockAction } from "./blockReducer.js";

const BlockContext = createContext<{
  state: BlockState;
  dispatch: React.Dispatch<BlockAction>;
} | null>(null);

export function BlockProvider({ children }: { children: ReactNode }): ReactNode {
  const [state, dispatch] = useReducer(blockReducer, INITIAL_BLOCK_STATE);
  return <BlockContext value={{ state, dispatch }}>{children}</BlockContext>;
}

export function useBlocks() {
  const context = use(BlockContext);
  if (!context) throw new Error("useBlocks must be used within BlockProvider");
  return context;
}
```

**Step 2: Create BlockEventRouter**

This bridges the existing notification methods to new BlockAction dispatches.

Create `tui/src/integration/BlockEventRouter.ts`:

```typescript
import { METHODS } from "../types/protocol.js";
import type { BlockAction } from "../state/blockReducer.js";

type Dispatch = (action: BlockAction) => void;

export class BlockEventRouter {
  private readonly dispatch: Dispatch;

  constructor(dispatch: Dispatch) {
    this.dispatch = dispatch;
  }

  handleNotification(method: string, params: Record<string, unknown>): void {
    switch (method) {
      case METHODS.STREAM_DELTA:
        this.dispatch({
          type: "STREAM_DELTA",
          delta: typeof params.delta === "string" ? params.delta : "",
        });
        return;

      case METHODS.TOOL_STARTED:
        this.dispatch({
          type: "TOOL_STARTED",
          name: typeof params.toolName === "string" ? params.toolName : "",
          callId: typeof params.callId === "string" ? params.callId : "",
          arguments: typeof params.arguments === "object" && params.arguments !== null
            ? (params.arguments as Record<string, unknown>)
            : {},
        });
        return;

      case METHODS.TOOL_COMPLETED:
        this.dispatch({
          type: "TOOL_COMPLETED",
          callId: typeof params.callId === "string" ? params.callId : "",
          result: typeof params.result === "string" ? params.result : undefined,
          error: typeof params.error === "string" && params.error.length > 0 ? params.error : undefined,
          durationMs: typeof params.durationMs === "number" ? params.durationMs : undefined,
        });
        return;

      case METHODS.RUN_COMPLETED: {
        const status = params.status;
        this.dispatch({
          type: "STREAM_END",
          status:
            status === "success" || status === "error" || status === "cancelled"
              ? status
              : "error",
          error: typeof params.error === "string" ? params.error : undefined,
        });
        return;
      }

      case METHODS.USAGE_UPDATE:
        this.dispatch({
          type: "UPDATE_USAGE",
          usage: {
            promptTokens: typeof params.promptTokens === "number" ? params.promptTokens : 0,
            completionTokens: typeof params.completionTokens === "number" ? params.completionTokens : 0,
            totalCost: typeof params.totalCost === "number" ? params.totalCost : 0,
            model: typeof params.model === "string" ? params.model : "",
            contextUsagePercent: typeof params.contextUsagePercent === "number" ? params.contextUsagePercent : 0,
          },
        });
        return;

      case METHODS.PERMISSION_REQUEST:
        this.dispatch({
          type: "PERMISSION_REQUEST",
          permission: {
            id: typeof params.requestId === "string" ? params.requestId : "",
            tool: typeof params.tool === "string" ? params.tool : "",
            arguments: typeof params.arguments === "object" && params.arguments !== null
              ? (params.arguments as Record<string, unknown>)
              : {},
            riskLevel:
              params.riskLevel === "low" || params.riskLevel === "medium" || params.riskLevel === "high"
                ? params.riskLevel
                : "medium",
            status: "pending",
          },
        });
        return;

      case METHODS.ERROR:
        this.dispatch({
          type: "SET_ERROR",
          error: typeof params.message === "string" ? params.message : "Unknown error",
        });
        return;

      case METHODS.COMPACTION_STARTED:
        this.dispatch({
          type: "ADD_SYSTEM_BLOCK",
          content: `Context compaction started: ${typeof params.reason === "string" ? params.reason : "unknown"}`,
        });
        return;

      case METHODS.BACKGROUND_COMPLETED:
        this.dispatch({
          type: "ADD_SYSTEM_BLOCK",
          content: `Background task ${typeof params.taskId === "string" ? params.taskId : ""} ${typeof params.status === "string" ? params.status : "completed"}`,
        });
        return;

      default:
        // Ignore unhandled notifications
        return;
    }
  }
}
```

**Step 3: Rewrite App.tsx**

Replace `tui/src/components/App.tsx` entirely. This is the big wiring change. The new AppShell uses `BlockProvider` + `useBlocks` instead of `AppProvider` + `useApp`:

```tsx
import { Box, Text, useInput } from "ink";
import React, { type ReactNode, useCallback, useEffect, useRef } from "react";
import { SageClient } from "../ipc/client.js";
import { SageClientContext, useSageClient } from "../ipc/hooks.js";
import { METHODS } from "../types/protocol.js";
import { BlockProvider, useBlocks } from "../state/BlockContext.js";
import { BlockEventRouter } from "../integration/BlockEventRouter.js";
import type { BlockState } from "../state/blockReducer.js";
import type { PermissionDecision } from "../types/state.js";
import { ConversationView } from "./ConversationView.js";
import { InputPrompt } from "./InputPrompt.js";
import { BottomBar } from "./BottomBar.js";
import { PermissionPrompt } from "./PermissionPrompt.js";
import { useResizeHandler } from "../hooks/useResizeHandler.js";

const NOTIFICATION_METHODS = [
  METHODS.STREAM_DELTA,
  METHODS.TOOL_STARTED,
  METHODS.TOOL_COMPLETED,
  METHODS.RUN_COMPLETED,
  METHODS.USAGE_UPDATE,
  METHODS.PERMISSION_REQUEST,
  METHODS.COMPACTION_STARTED,
  METHODS.BACKGROUND_COMPLETED,
  METHODS.ERROR,
] as const;

function AppShell(): ReactNode {
  const { state, dispatch } = useBlocks();
  const client = useSageClient();
  const { width: columns } = useResizeHandler();
  const stateRef = useRef<BlockState>(state);
  stateRef.current = state;

  useEffect(() => {
    const router = new BlockEventRouter(dispatch);

    const unsubscribers = NOTIFICATION_METHODS.map((method) =>
      client.onNotification(method, (params) => {
        router.handleNotification(method, params);
      }),
    );

    client.spawn().catch((err: unknown) => {
      dispatch({
        type: "SET_ERROR",
        error: err instanceof Error ? err.message : "Failed to connect to backend",
      });
    });

    return () => {
      for (const unsub of unsubscribers) {
        unsub();
      }
      client.dispose();
    };
  }, [client, dispatch]);

  const handleSubmit = useCallback(
    async (text: string) => {
      if (client.status !== "connected") return;

      dispatch({ type: "SUBMIT_MESSAGE", content: text });

      try {
        const result = await client.request(METHODS.AGENT_RUN, { message: text });
        const runId =
          typeof result === "object" && result !== null && "runId" in result
            ? String((result as Record<string, unknown>).runId)
            : `run_${Date.now()}`;
        dispatch({ type: "STREAM_START", runId });
      } catch (err: unknown) {
        dispatch({
          type: "SET_ERROR",
          error: err instanceof Error ? err.message : "Failed to send message",
        });
      }
    },
    [client, dispatch],
  );

  const handleCancel = useCallback(async () => {
    dispatch({ type: "STREAM_END", status: "cancelled" });
    try {
      await client.request(METHODS.AGENT_CANCEL, {});
    } catch {
      // Best effort
    }
  }, [client, dispatch]);

  const handlePermissionRespond = useCallback(
    async (id: string, decision: PermissionDecision) => {
      dispatch({ type: "PERMISSION_RESPOND", id, decision });
      try {
        await client.request(METHODS.PERMISSION_RESPOND, {
          request_id: id,
          decision,
        });
      } catch {
        // Best effort
      }
    },
    [client, dispatch],
  );

  useInput((input, key) => {
    if (key.ctrl && input === "c") {
      if (state.activeStream) {
        void handleCancel();
      } else {
        process.exit(0);
      }
      return;
    }
    if (key.escape) {
      if (state.activeStream) {
        void handleCancel();
      } else if (state.error) {
        dispatch({ type: "CLEAR_ERROR" });
      }
    }
  });

  const pendingPermissions = state.permissions.filter((p) => p.status === "pending");

  return (
    <Box flexDirection="column" width={columns}>
      <ConversationView
        completedBlocks={state.completedBlocks}
        activeStream={state.activeStream}
      />
      {state.error && (
        <Box>
          <Text color="red">{"● Error: "}{state.error}</Text>
          <Text dimColor>{" (ESC to dismiss)"}</Text>
        </Box>
      )}
      {pendingPermissions.map((perm) => (
        <PermissionPrompt
          key={perm.id}
          request={perm}
          onRespond={handlePermissionRespond}
        />
      ))}
      <InputPrompt onSubmit={handleSubmit} isActive={!state.activeStream} />
      <BottomBar usage={state.usage} />
    </Box>
  );
}

export function App(): ReactNode {
  const clientRef = useRef(new SageClient());

  return (
    <SageClientContext value={clientRef.current}>
      <BlockProvider>
        <AppShell />
      </BlockProvider>
    </SageClientContext>
  );
}
```

**Step 4: Verify types compile**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx tsc --noEmit`

Fix any import issues. The key change: `App` no longer uses `AppProvider`, `PlanProvider`, `useApp`, or `wireIntegration`. It uses `BlockProvider`, `useBlocks`, and `BlockEventRouter` directly.

**Step 5: Run tests**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run`

Some old tests referencing the old `App` component structure may fail — that's expected and will be handled in Task 8.

**Step 6: Commit**

```bash
git add tui/src/state/BlockContext.tsx tui/src/integration/BlockEventRouter.ts tui/src/components/App.tsx
git commit -m "feat(tui): wire new block-based architecture into AppShell"
```

---

### Task 8: Update tests and clean up old components

**Files:**
- Modify: `tui/src/components/__tests__/App.test.tsx`
- Modify: `tui/src/App.test.tsx` (if exists)

**Step 1: Update App tests**

The old App tests reference `AppProvider`, `useApp`, old `ChatView`, etc. Update them to test the new block-based architecture. Read the existing test files first, then update them to match the new component structure.

Key changes:
- `AppProvider` -> `BlockProvider`
- `useApp` -> `useBlocks`
- `ChatView` -> `ConversationView`
- `MessageBubble` -> `StaticBlock`
- `SET_STREAMING` -> `STREAM_START` / `STREAM_END`
- `ADD_MESSAGE` -> `SUBMIT_MESSAGE`

**Step 2: Run full test suite**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run`

Fix any remaining failures. The old tests for `ChatView`, `MessageBubble`, `StatusBar` may need removal if those components are no longer used.

**Step 3: Type check**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx tsc --noEmit`

**Step 4: Build**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && pnpm build`

**Step 5: Commit**

```bash
git add -A
git commit -m "test(tui): update tests for block-based architecture"
```

---

### Task 9: Build, install, and smoke test

**Step 1: Full verification**

```bash
cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run
cd /Users/sachoi/sagebynature/sage-agent/tui && npx tsc --noEmit
cd /Users/sachoi/sagebynature/sage-agent/tui && pnpm build
cd /Users/sachoi/sagebynature/sage-agent && uv tool install --editable .
```

**Step 2: Smoke test**

```bash
cd ~/github/sage-assistant && sage-tui
```

Verify:
- Agent output renders with `●` prefix and markdown formatting
- Code blocks have syntax highlighting
- User messages show with `>` prefix, dimmed
- Tool calls appear inline as `● toolName path`
- Thinking state shows `✻ Thinking...` with spinner
- Status bar shows model, context %, cost
- Terminal native scroll works (scroll up to see earlier output)
- Ctrl+C cancels during streaming
- `/help` shows command list

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat(tui): complete UX overhaul — Claude Code-inspired block architecture"
```

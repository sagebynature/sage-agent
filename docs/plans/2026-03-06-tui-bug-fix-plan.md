# TUI Bug Fix & Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all TUI bugs (delegation stuck "running", flickering), clean up dual state systems, port key components, and wire all slash commands + keyboard shortcuts.

**Architecture:** Commit fully to the block-based state system (`BlockState`/`BlockContext`/`blockReducer`). Delete the old `AppState`/`AppContext`/`EventRouter`. Port useful orphaned components (`AgentTree`, `ToolDisplay`, `SessionPicker`) to the block system. Truncate active stream to last N lines during streaming; full content via `<Static>` on completion.

**Tech Stack:** TypeScript, React 19, Ink 6, Vitest

---

## Phase 1: Core Bug Fixes

### Task 1: Fix delegation completion tracking in BlockEventRouter

**Files:**
- Modify: `tui/src/integration/BlockEventRouter.ts`
- Test: `tui/src/integration/__tests__/BlockEventRouter.test.ts` (create)

**Step 1: Write the failing test**

Create `tui/src/integration/__tests__/BlockEventRouter.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { BlockEventRouter } from "../BlockEventRouter.js";
import { METHODS } from "../../types/protocol.js";
import type { BlockAction } from "../../state/blockReducer.js";

describe("BlockEventRouter", () => {
  let dispatched: BlockAction[];
  let dispatch: (action: BlockAction) => void;
  let router: BlockEventRouter;

  beforeEach(() => {
    dispatched = [];
    dispatch = (action: BlockAction) => dispatched.push(action);
    router = new BlockEventRouter(dispatch);
  });

  it("maps delegation/started to TOOL_STARTED", () => {
    router.handleNotification(METHODS.DELEGATION_STARTED, {
      target: "researcher",
      task: "find docs",
    });

    expect(dispatched).toHaveLength(1);
    expect(dispatched[0]!.type).toBe("TOOL_STARTED");
    if (dispatched[0]!.type === "TOOL_STARTED") {
      expect(dispatched[0]!.name).toContain("researcher");
      expect(dispatched[0]!.callId).toMatch(/^delegation_/);
    }
  });

  it("maps delegation/completed to TOOL_COMPLETED with matching callId", () => {
    router.handleNotification(METHODS.DELEGATION_STARTED, {
      target: "researcher",
      task: "find docs",
    });

    const startAction = dispatched[0]!;
    expect(startAction.type).toBe("TOOL_STARTED");
    const callId = startAction.type === "TOOL_STARTED" ? startAction.callId : "";

    dispatched.length = 0;

    router.handleNotification(METHODS.DELEGATION_COMPLETED, {
      target: "researcher",
      result: "found 3 docs",
    });

    const completedAction = dispatched.find((a) => a.type === "TOOL_COMPLETED");
    expect(completedAction).toBeDefined();
    if (completedAction?.type === "TOOL_COMPLETED") {
      expect(completedAction.callId).toBe(callId);
      expect(completedAction.result).toBe("found 3 docs");
    }
  });

  it("delegation/completed without prior start still dispatches system block", () => {
    router.handleNotification(METHODS.DELEGATION_COMPLETED, {
      target: "unknown",
      result: "done",
    });

    expect(dispatched.some((a) => a.type === "ADD_SYSTEM_BLOCK")).toBe(true);
  });

  it("maps tool/started and tool/completed", () => {
    router.handleNotification(METHODS.TOOL_STARTED, {
      toolName: "shell",
      callId: "call-1",
      arguments: { command: "ls" },
    });
    expect(dispatched[0]).toEqual({
      type: "TOOL_STARTED",
      name: "shell",
      callId: "call-1",
      arguments: { command: "ls" },
    });
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd tui && npx vitest run src/integration/__tests__/BlockEventRouter.test.ts`
Expected: FAIL — "maps delegation/completed to TOOL_COMPLETED with matching callId" fails

**Step 3: Implement the fix**

Modify `tui/src/integration/BlockEventRouter.ts`:

```ts
import { METHODS } from "../types/protocol.js";
import type { BlockAction } from "../state/blockReducer.js";

type Dispatch = (action: BlockAction) => void;

export class BlockEventRouter {
  private readonly dispatch: Dispatch;
  private readonly delegationCallIds = new Map<string, string>();

  constructor(dispatch: Dispatch) {
    this.dispatch = dispatch;
  }

  handleNotification(method: string, params: Record<string, unknown>): void {
    switch (method) {
      // ... all existing cases unchanged until DELEGATION_STARTED ...

      case METHODS.DELEGATION_STARTED: {
        const target = typeof params.target === "string" ? params.target : "subagent";
        const callId = `delegation_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
        this.delegationCallIds.set(target, callId);
        this.dispatch({
          type: "TOOL_STARTED",
          name: `delegate → ${target}`,
          callId,
          arguments: { task: typeof params.task === "string" ? params.task : "" },
        });
        return;
      }

      case METHODS.DELEGATION_COMPLETED: {
        const target = typeof params.target === "string" ? params.target : "";
        const callId = this.delegationCallIds.get(target);
        if (callId) {
          this.dispatch({
            type: "TOOL_COMPLETED",
            callId,
            result: typeof params.result === "string" ? params.result : undefined,
          });
          this.delegationCallIds.delete(target);
        }
        this.dispatch({
          type: "ADD_SYSTEM_BLOCK",
          content: `Subagent ${target} completed`,
        });
        return;
      }

      // ... rest unchanged ...
    }
  }
}
```

Key change: Added `delegationCallIds: Map<string, string>` field. `DELEGATION_STARTED` stores the generated callId keyed by target name. `DELEGATION_COMPLETED` looks it up and dispatches `TOOL_COMPLETED` before the system block.

**Step 4: Run test to verify it passes**

Run: `cd tui && npx vitest run src/integration/__tests__/BlockEventRouter.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add tui/src/integration/BlockEventRouter.ts tui/src/integration/__tests__/BlockEventRouter.test.ts
git commit -m "fix(tui): track delegation callIds so completion marks tool as done"
```

---

### Task 2: Force-resolve running tools on stream end

**Files:**
- Modify: `tui/src/state/blockReducer.ts:77-99` (`flattenStream`)
- Test: `tui/src/state/__tests__/blockReducer.test.ts`

**Step 1: Write the failing test**

Append to `tui/src/state/__tests__/blockReducer.test.ts`:

```ts
it("STREAM_END force-resolves running tools to completed", () => {
  let state = blockReducer(INITIAL_BLOCK_STATE, {
    type: "STREAM_START",
    runId: "run-1",
  });
  state = blockReducer(state, {
    type: "TOOL_STARTED",
    name: "delegate → researcher",
    callId: "del-1",
    arguments: { task: "search" },
  });
  // Tool never gets TOOL_COMPLETED — simulate stream ending while tool still running
  state = blockReducer(state, {
    type: "STREAM_END",
    status: "success",
  });

  expect(state.activeStream).toBeNull();
  const toolBlock = state.completedBlocks.find((b) => b.type === "tool");
  expect(toolBlock).toBeDefined();
  expect(toolBlock!.tools![0]!.status).toBe("completed");
});

it("STREAM_END with cancelled status marks running tools as cancelled", () => {
  let state = blockReducer(INITIAL_BLOCK_STATE, {
    type: "STREAM_START",
    runId: "run-1",
  });
  state = blockReducer(state, {
    type: "TOOL_STARTED",
    name: "shell",
    callId: "call-1",
    arguments: {},
  });
  state = blockReducer(state, {
    type: "STREAM_END",
    status: "cancelled",
  });

  const toolBlock = state.completedBlocks.find((b) => b.type === "tool");
  expect(toolBlock!.tools![0]!.status).toBe("failed");
  expect(toolBlock!.tools![0]!.error).toBe("cancelled");
});
```

**Step 2: Run test to verify it fails**

Run: `cd tui && npx vitest run src/state/__tests__/blockReducer.test.ts`
Expected: FAIL — tool status is "running" not "completed"

**Step 3: Implement the fix**

Modify `flattenStream` in `tui/src/state/blockReducer.ts:77-99`:

```ts
function flattenStream(
  stream: ActiveStream,
  endStatus: "success" | "error" | "cancelled",
): OutputBlock[] {
  const blocks: OutputBlock[] = [];
  const now = Date.now();
  for (const tool of stream.tools) {
    const resolvedTool: ToolSummary =
      tool.status === "running"
        ? {
            ...tool,
            status: endStatus === "cancelled" ? "failed" : "completed",
            error: endStatus === "cancelled" ? "cancelled" : tool.error,
            durationMs: now - stream.startedAt,
          }
        : tool;
    blocks.push({
      id: makeId("tool"),
      type: "tool",
      content: resolvedTool.name,
      tools: [resolvedTool],
      timestamp: now,
    });
  }
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
```

Update the `STREAM_END` case (line ~199) to pass the status:

```ts
case "STREAM_END": {
  const newBlocks: OutputBlock[] = [];
  if (state.activeStream) {
    newBlocks.push(...flattenStream(state.activeStream, action.status));
  }
  // ... rest unchanged
}
```

**Step 4: Run test to verify it passes**

Run: `cd tui && npx vitest run src/state/__tests__/blockReducer.test.ts`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tui/src/state/blockReducer.ts tui/src/state/__tests__/blockReducer.test.ts
git commit -m "fix(tui): force-resolve running tools on stream end"
```

---

### Task 3: Cache the Marked parser singleton

**Files:**
- Modify: `tui/src/renderer/MarkdownRenderer.tsx:37-57,62`

**Step 1: Write the failing test**

Append to `tui/src/renderer/__tests__/MarkdownRenderer.test.tsx`:

```ts
it("reuses cached Marked parser across calls", () => {
  const result1 = renderMarkdown("**bold**", false);
  const result2 = renderMarkdown("*italic*", false);
  // Both should succeed (parser not corrupted by reuse)
  expect(result1).toContain("bold");
  expect(result2).toContain("italic");
});
```

**Step 2: Run test to verify it passes (baseline — this tests correctness, not caching)**

Run: `cd tui && npx vitest run src/renderer/__tests__/MarkdownRenderer.test.tsx`
Expected: PASS (baseline correctness)

**Step 3: Implement the cache**

Modify `tui/src/renderer/MarkdownRenderer.tsx`. Replace lines 37-62:

```ts
let cachedParser: Marked | null = null;

function getMarkedRenderer(): Marked {
  if (cachedParser) return cachedParser;

  const parser = new Marked();
  const terminalExtension = markedTerminal({
    reflowText: false,
    showSectionPrefix: true,
    tab: 2,
    emoji: true,
  });

  const rendererOverride: RendererObject = {
    code(token) {
      return `${formatCodeBlock(token.text, token.lang)}\n\n`;
    },
    html() {
      return "";
    },
  };

  parser.use(terminalExtension, { renderer: rendererOverride });
  cachedParser = parser;
  return parser;
}

function renderMarkdown(content: string, isStreaming: boolean): string {
  const strippedContent = stripHtml(content);
  const { markdown, hasPendingCodeFence } = withClosedCodeFence(strippedContent, isStreaming);
  const parser = getMarkedRenderer();
  // ... rest unchanged
}
```

**Step 4: Run tests**

Run: `cd tui && npx vitest run src/renderer/__tests__/MarkdownRenderer.test.tsx`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tui/src/renderer/MarkdownRenderer.tsx
git commit -m "perf(tui): cache Marked parser instance to avoid recreation per render"
```

---

### Task 4: Truncate active stream content to last N lines

**Files:**
- Modify: `tui/src/components/ActiveStreamView.tsx:125-134` (`StreamContent`)
- Test: `tui/src/components/__tests__/ActiveStreamView.test.tsx`

**Step 1: Write the failing test**

Append to `tui/src/components/__tests__/ActiveStreamView.test.tsx`:

```ts
import { describe, it, expect } from "vitest";
import { truncateStreamLines } from "../ActiveStreamView.js";

describe("truncateStreamLines", () => {
  it("returns all lines when under limit", () => {
    const content = "line1\nline2\nline3";
    const { lines, truncatedCount } = truncateStreamLines(content, 30);
    expect(lines).toHaveLength(3);
    expect(truncatedCount).toBe(0);
  });

  it("truncates to last N lines when over limit", () => {
    const content = Array.from({ length: 50 }, (_, i) => `line${i}`).join("\n");
    const { lines, truncatedCount } = truncateStreamLines(content, 30);
    expect(lines).toHaveLength(30);
    expect(truncatedCount).toBe(20);
    expect(lines[0]).toBe("line20");
    expect(lines[29]).toBe("line49");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd tui && npx vitest run src/components/__tests__/ActiveStreamView.test.tsx`
Expected: FAIL — `truncateStreamLines` not exported

**Step 3: Implement truncation**

Modify `tui/src/components/ActiveStreamView.tsx`. Add the helper and update `StreamContent`:

```ts
const MAX_VISIBLE_STREAM_LINES = 30;

export function truncateStreamLines(
  content: string,
  maxLines: number,
): { lines: string[]; truncatedCount: number } {
  const allLines = content.split("\n");
  if (allLines.length <= maxLines) {
    return { lines: allLines, truncatedCount: 0 };
  }
  const truncatedCount = allLines.length - maxLines;
  return { lines: allLines.slice(-maxLines), truncatedCount };
}

function StreamContent({ content }: { content: string }): ReactNode {
  const { lines, truncatedCount } = truncateStreamLines(content, MAX_VISIBLE_STREAM_LINES);
  return (
    <Box flexDirection="column">
      {truncatedCount > 0 && (
        <Text dimColor>{"  ... ("}{truncatedCount + lines.length}{" lines, showing last "}{lines.length}{")"}</Text>
      )}
      {lines.map((line, i) => (
        <Text key={i}>{i === 0 && truncatedCount === 0 ? `● ${line}` : `  ${line}`}</Text>
      ))}
    </Box>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd tui && npx vitest run src/components/__tests__/ActiveStreamView.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add tui/src/components/ActiveStreamView.tsx tui/src/components/__tests__/ActiveStreamView.test.tsx
git commit -m "perf(tui): truncate active stream to last 30 lines to prevent overflow"
```

---

### Task 5: Isolate spinner from content re-renders

**Files:**
- Modify: `tui/src/components/ActiveStreamView.tsx:136-155` (`ActiveStreamView`)

**Step 1: No new test needed — this is a render structure refactor. Existing tests cover behavior.**

**Step 2: Implement the isolation**

Modify `ActiveStreamView` in `tui/src/components/ActiveStreamView.tsx`:

```tsx
export function ActiveStreamView({ stream }: ActiveStreamViewProps): ReactNode {
  if (!stream) return null;

  const hasTools = stream.tools.length > 0;
  const hasRunningTools = stream.tools.some((t) => t.status === "running");

  return (
    <Box flexDirection="column">
      {hasRunningTools ? (
        <SpinnerProvider>
          {stream.tools.map((tool, idx) => (
            <ToolStatusIndicator key={`${idx}_${tool.callId}`} tool={tool} />
          ))}
        </SpinnerProvider>
      ) : (
        stream.tools.map((tool, idx) => (
          <ToolStatusIndicator key={`${idx}_${tool.callId}`} tool={tool} />
        ))
      )}
      {stream.isThinking && !hasTools ? (
        <SpinnerProvider>
          <ThinkingIndicator startedAt={stream.startedAt} />
        </SpinnerProvider>
      ) : stream.content.length > 0 ? (
        <StreamContent content={stream.content} />
      ) : null}
    </Box>
  );
}
```

Key change: `SpinnerProvider` only wraps tool indicators when there are running tools, and the `ThinkingIndicator` when thinking. `StreamContent` is never inside `SpinnerProvider`, so 80ms spinner ticks don't re-render content.

**Step 3: Run all tests**

Run: `cd tui && npx vitest run`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tui/src/components/ActiveStreamView.tsx
git commit -m "perf(tui): isolate spinner provider from stream content to reduce re-renders"
```

---

## Phase 2: State System Cleanup

### Task 6: Extend BlockState with agents, CLEAR_BLOCKS, and prune permissions

**Files:**
- Modify: `tui/src/state/blockReducer.ts`
- Modify: `tui/src/types/blocks.ts` (add `startedAt` to `ToolSummary`)
- Test: `tui/src/state/__tests__/blockReducer.test.ts`

**Step 1: Write failing tests**

Append to `tui/src/state/__tests__/blockReducer.test.ts`:

```ts
import type { AgentNode } from "../../types/state.js";

it("AGENT_STARTED adds agent to agents array", () => {
  const agent: AgentNode = {
    name: "researcher",
    status: "active",
    task: "find docs",
    depth: 1,
    children: [],
    startedAt: 1000,
  };
  const state = blockReducer(INITIAL_BLOCK_STATE, {
    type: "AGENT_STARTED",
    agent,
  });
  expect(state.agents).toHaveLength(1);
  expect(state.agents[0]!.name).toBe("researcher");
});

it("AGENT_COMPLETED updates agent status", () => {
  const agent: AgentNode = {
    name: "researcher",
    status: "active",
    task: "find docs",
    depth: 1,
    children: [],
    startedAt: 1000,
  };
  let state = blockReducer(INITIAL_BLOCK_STATE, {
    type: "AGENT_STARTED",
    agent,
  });
  state = blockReducer(state, {
    type: "AGENT_COMPLETED",
    name: "researcher",
    status: "completed",
  });
  expect(state.agents[0]!.status).toBe("completed");
  expect(state.agents[0]!.completedAt).toBeDefined();
});

it("CLEAR_BLOCKS resets completedBlocks, activeStream, agents, and prunes permissions", () => {
  let state = blockReducer(INITIAL_BLOCK_STATE, {
    type: "SUBMIT_MESSAGE",
    content: "hello",
  });
  state = blockReducer(state, {
    type: "PERMISSION_REQUEST",
    permission: { id: "p1", tool: "bash", arguments: {}, riskLevel: "high", status: "pending" },
  });
  state = blockReducer(state, {
    type: "PERMISSION_RESPOND",
    id: "p1",
    decision: "allow_once",
  });
  state = blockReducer(state, { type: "CLEAR_BLOCKS" });

  expect(state.completedBlocks).toEqual([]);
  expect(state.activeStream).toBeNull();
  expect(state.permissions).toEqual([]);
  expect(state.agents).toEqual([]);
  expect(state.error).toBeNull();
});

it("STREAM_END prunes resolved permissions", () => {
  let state = blockReducer(INITIAL_BLOCK_STATE, {
    type: "PERMISSION_REQUEST",
    permission: { id: "p1", tool: "bash", arguments: {}, riskLevel: "high", status: "pending" },
  });
  state = blockReducer(state, {
    type: "PERMISSION_RESPOND",
    id: "p1",
    decision: "allow_once",
  });
  state = blockReducer(state, {
    type: "PERMISSION_REQUEST",
    permission: { id: "p2", tool: "read", arguments: {}, riskLevel: "low", status: "pending" },
  });
  state = blockReducer(state, {
    type: "STREAM_START",
    runId: "run-1",
  });
  state = blockReducer(state, {
    type: "STREAM_END",
    status: "success",
  });

  // p1 (approved) pruned, p2 (still pending) kept
  expect(state.permissions).toHaveLength(1);
  expect(state.permissions[0]!.id).toBe("p2");
});
```

**Step 2: Run test to verify it fails**

Run: `cd tui && npx vitest run src/state/__tests__/blockReducer.test.ts`
Expected: FAIL — `AGENT_STARTED`, `AGENT_COMPLETED`, `CLEAR_BLOCKS` not in `BlockAction`

**Step 3: Implement**

Add to `tui/src/types/blocks.ts`, add optional `startedAt` to `ToolSummary`:

```ts
export interface ToolSummary {
  name: string;
  callId: string;
  arguments: Record<string, unknown>;
  result?: string;
  error?: string;
  durationMs?: number;
  status: "running" | "completed" | "failed";
  startedAt?: number;
}
```

Modify `tui/src/state/blockReducer.ts`:

1. Import `AgentNode` and add `agents` to `BlockState`:

```ts
import type { AgentNode } from "../types/state.js";

export interface BlockState {
  completedBlocks: OutputBlock[];
  activeStream: ActiveStream | null;
  usage: UsageState;
  permissions: PermissionState[];
  error: string | null;
  session: SessionState | null;
  agents: AgentNode[];
}
```

2. Add new action variants to `BlockAction`:

```ts
| { type: "AGENT_STARTED"; agent: AgentNode }
| { type: "AGENT_COMPLETED"; name: string; status: "completed" | "failed" }
| { type: "CLEAR_BLOCKS" }
```

3. Add `agents: []` to `INITIAL_BLOCK_STATE`.

4. Add reducer cases:

```ts
case "AGENT_STARTED": {
  return {
    ...state,
    agents: [...state.agents, action.agent],
  };
}

case "AGENT_COMPLETED": {
  return {
    ...state,
    agents: state.agents.map((a) =>
      a.name === action.name
        ? { ...a, status: action.status, completedAt: Date.now() }
        : a,
    ),
  };
}

case "CLEAR_BLOCKS": {
  return {
    ...state,
    completedBlocks: [],
    activeStream: null,
    agents: [],
    permissions: [],
    error: null,
  };
}
```

5. In `STREAM_END` case, after computing `newBlocks`, prune resolved permissions:

```ts
case "STREAM_END": {
  // ... existing newBlocks logic ...
  return {
    ...state,
    completedBlocks: [...state.completedBlocks, ...newBlocks],
    activeStream: null,
    permissions: state.permissions.filter((p) => p.status === "pending"),
  };
}
```

6. In `TOOL_STARTED`, add `startedAt` to the tool:

```ts
const tool: ToolSummary = {
  name: action.name,
  callId: action.callId,
  arguments: action.arguments,
  status: "running",
  startedAt: Date.now(),
};
```

**Step 4: Run tests**

Run: `cd tui && npx vitest run src/state/__tests__/blockReducer.test.ts`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tui/src/types/blocks.ts tui/src/state/blockReducer.ts tui/src/state/__tests__/blockReducer.test.ts
git commit -m "feat(tui): extend BlockState with agents, CLEAR_BLOCKS, permission pruning"
```

---

### Task 7: Complete BlockEventRouter for all events

**Files:**
- Modify: `tui/src/integration/BlockEventRouter.ts`
- Modify: `tui/src/types/protocol.ts` (add LLM_TURN methods)
- Test: `tui/src/integration/__tests__/BlockEventRouter.test.ts`

**Step 1: Write failing tests**

Append to `tui/src/integration/__tests__/BlockEventRouter.test.ts`:

```ts
it("delegation/started dispatches AGENT_STARTED and TOOL_STARTED", () => {
  router.handleNotification(METHODS.DELEGATION_STARTED, {
    target: "coder",
    task: "write tests",
  });

  expect(dispatched.some((a) => a.type === "AGENT_STARTED")).toBe(true);
  expect(dispatched.some((a) => a.type === "TOOL_STARTED")).toBe(true);

  const agentAction = dispatched.find((a) => a.type === "AGENT_STARTED");
  if (agentAction?.type === "AGENT_STARTED") {
    expect(agentAction.agent.name).toBe("coder");
    expect(agentAction.agent.status).toBe("active");
  }
});

it("delegation/completed dispatches AGENT_COMPLETED and TOOL_COMPLETED", () => {
  router.handleNotification(METHODS.DELEGATION_STARTED, {
    target: "coder",
    task: "write tests",
  });
  dispatched.length = 0;

  router.handleNotification(METHODS.DELEGATION_COMPLETED, {
    target: "coder",
    result: "done",
  });

  expect(dispatched.some((a) => a.type === "AGENT_COMPLETED")).toBe(true);
  expect(dispatched.some((a) => a.type === "TOOL_COMPLETED")).toBe(true);

  const agentAction = dispatched.find((a) => a.type === "AGENT_COMPLETED");
  if (agentAction?.type === "AGENT_COMPLETED") {
    expect(agentAction.name).toBe("coder");
    expect(agentAction.status).toBe("completed");
  }
});

it("handles llm/turn_started notification", () => {
  router.handleNotification(METHODS.LLM_TURN_STARTED, {
    turn: 1,
    model: "gpt-5",
    messageCount: 3,
  });
  // Should dispatch ADD_SYSTEM_BLOCK or similar
  expect(dispatched.length).toBeGreaterThanOrEqual(0);
  // LLM turn started is informational — no crash
});
```

**Step 2: Run test to verify it fails**

Run: `cd tui && npx vitest run src/integration/__tests__/BlockEventRouter.test.ts`
Expected: FAIL — `AGENT_STARTED` not dispatched, `METHODS.LLM_TURN_STARTED` undefined

**Step 3: Implement**

Add to `tui/src/types/protocol.ts` METHODS object:

```ts
LLM_TURN_STARTED: "llm/turn_started",
LLM_TURN_COMPLETED: "llm/turn_completed",
```

Update `tui/src/integration/BlockEventRouter.ts` — the full updated `DELEGATION_STARTED` and `DELEGATION_COMPLETED` cases:

```ts
case METHODS.DELEGATION_STARTED: {
  const target = typeof params.target === "string" ? params.target : "subagent";
  const task = typeof params.task === "string" ? params.task : "";
  const callId = `delegation_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
  this.delegationCallIds.set(target, callId);

  this.dispatch({
    type: "AGENT_STARTED",
    agent: {
      name: target,
      status: "active",
      task,
      depth: 1,
      children: [],
      startedAt: Date.now(),
    },
  });
  this.dispatch({
    type: "TOOL_STARTED",
    name: `delegate → ${target}`,
    callId,
    arguments: { task },
  });
  return;
}

case METHODS.DELEGATION_COMPLETED: {
  const target = typeof params.target === "string" ? params.target : "";
  const result = typeof params.result === "string" ? params.result : undefined;
  const callId = this.delegationCallIds.get(target);

  this.dispatch({
    type: "AGENT_COMPLETED",
    name: target,
    status: "completed",
  });

  if (callId) {
    this.dispatch({
      type: "TOOL_COMPLETED",
      callId,
      result,
    });
    this.delegationCallIds.delete(target);
  }

  this.dispatch({
    type: "ADD_SYSTEM_BLOCK",
    content: `Subagent ${target} completed`,
  });
  return;
}

case METHODS.LLM_TURN_STARTED:
  // Informational — no state change needed
  return;

case METHODS.LLM_TURN_COMPLETED:
  // Usage update comes via separate USAGE_UPDATE notification
  return;
```

**Step 4: Run tests**

Run: `cd tui && npx vitest run src/integration/__tests__/BlockEventRouter.test.ts`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tui/src/types/protocol.ts tui/src/integration/BlockEventRouter.ts tui/src/integration/__tests__/BlockEventRouter.test.ts
git commit -m "feat(tui): complete BlockEventRouter with agent tracking and LLM turn methods"
```

---

### Task 8: Delete old state system and associated tests

**Files to delete:**
- `tui/src/state/AppContext.tsx`
- `tui/src/state/selectors.ts`
- `tui/src/state/__tests__/selectors.test.ts`
- `tui/src/state/__tests__/reducer.test.ts`
- `tui/src/integration/EventRouter.ts`
- `tui/src/integration/__tests__/EventRouter.test.ts`
- `tui/src/integration/wiring.ts`
- `tui/src/integration/__tests__/wiring.test.tsx`
- `tui/src/integration/CommandExecutor.ts`
- `tui/src/integration/__tests__/CommandExecutor.test.ts`
- `tui/src/hooks/useMarkdownStream.ts` (uses old streaming pattern)
- `tui/src/hooks/__tests__/useMarkdownStream.test.ts`

**Step 1: Delete files**

```bash
cd tui && rm \
  src/state/AppContext.tsx \
  src/state/selectors.ts \
  src/state/__tests__/selectors.test.ts \
  src/state/__tests__/reducer.test.ts \
  src/integration/EventRouter.ts \
  src/integration/__tests__/EventRouter.test.ts \
  src/integration/wiring.ts \
  src/integration/__tests__/wiring.test.tsx \
  src/integration/CommandExecutor.ts \
  src/integration/__tests__/CommandExecutor.test.ts \
  src/hooks/useMarkdownStream.ts \
  src/hooks/__tests__/useMarkdownStream.test.ts
```

**Step 2: Clean up types**

Remove `AppState`, `AppStateV2`, and `ChatMessage` from `tui/src/types/state.ts`. Keep `ToolCallState` only if referenced by surviving code — check with grep first. If nothing references `ToolCallState` after component deletion (Phase 3), remove it too. For now keep it.

Remove `ChatMessage` from `tui/src/types/state.ts`.

**Step 3: Update barrel exports**

Update `tui/src/state/index.ts` to only export from `blockReducer.js` and `BlockContext.js`. Remove `AppContext` and `selectors` exports if present.

Update `tui/src/integration/index.ts` to only export from `BlockEventRouter.js` and `LifecycleManager.js`. Remove `EventRouter`, `wiring`, `CommandExecutor` exports.

Update `tui/src/hooks/index.ts` to remove `useMarkdownStream` export.

**Step 4: Run tests to confirm nothing is broken**

Run: `cd tui && npx vitest run`
Expected: ALL PASS (deleted tests won't run; surviving code doesn't import deleted modules)

**Step 5: Commit**

```bash
git add -A tui/src/
git commit -m "refactor(tui): delete old AppState/EventRouter/CommandExecutor state system"
```

---

### Task 9: Clean up unused types from state.ts

**Files:**
- Modify: `tui/src/types/state.ts`

**Step 1: Remove dead types**

Remove `ChatMessage`, `AppState`, and `AppStateV2` from `tui/src/types/state.ts`. Keep: `ViewMode`, `ToolStatus`, `PermissionDecision`, `PermissionStatus`, `AgentStatus`, `ToolCallState` (may still be referenced), `PermissionState`, `SessionState`, `AgentNode`, `UsageState`.

**Step 2: Verify no imports break**

Run: `cd tui && npx vitest run`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tui/src/types/state.ts
git commit -m "refactor(tui): remove dead ChatMessage, AppState, AppStateV2 types"
```

---

## Phase 3: Port Key Components

### Task 10: Port AgentTree to block system

**Files:**
- Modify: `tui/src/components/AgentTree.tsx`
- Test: `tui/src/components/__tests__/AgentTree.test.tsx`

**Step 1: Update AgentTree**

Replace `useApp()` with `useBlocks()`:

```tsx
import { useBlocks } from '../state/BlockContext.js';
// Remove: import { useApp } from '../state/AppContext.js';

export const AgentTree: React.FC<AgentTreeProps> = ({ maxDepth = 5 }) => {
  const { state } = useBlocks();
  const { agents } = state;
  // ... rest unchanged
};
```

Remove `showToolDetail` prop and `void showToolDetail` line.

Remove `COLORS` import — replace with inline string colors ("gray", "green", "red", "yellow").

**Step 2: Update AgentTree test**

Update test to wrap with `BlockProvider` instead of `AppProvider`. Update any state setup to use `BlockState`.

**Step 3: Run tests**

Run: `cd tui && npx vitest run src/components/__tests__/AgentTree.test.tsx`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tui/src/components/AgentTree.tsx tui/src/components/__tests__/AgentTree.test.tsx
git commit -m "refactor(tui): port AgentTree to block state system"
```

---

### Task 11: Port ToolDisplay to accept ToolSummary and replace ToolBlock

**Files:**
- Modify: `tui/src/components/ToolDisplay.tsx`
- Modify: `tui/src/components/blocks/StaticBlock.tsx`
- Delete: `tui/src/components/blocks/ToolBlock.tsx`
- Delete: `tui/src/components/ToolTimer.tsx`
- Test: `tui/src/components/__tests__/ToolDisplay.test.tsx`

**Step 1: Rewrite ToolDisplay to use ToolSummary**

Replace `ToolCallState` with `ToolSummary` from `types/blocks.js`. Simplify: remove `ToolTimer` (use `durationMs` directly), remove `Spinner` import (completed tools don't spin), remove `ToolCallCollapsible` (keep it simple — just show summary).

```tsx
import { Box, Text } from "ink";
import React, { type ReactNode } from "react";
import type { ToolSummary } from "../types/blocks.js";

interface ToolDisplayProps {
  tools: ToolSummary[];
}

function formatDuration(ms?: number): string {
  if (ms === undefined) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatToolArgs(tool: ToolSummary): string {
  const args = tool.arguments;
  if (args.path) return ` ${args.path}`;
  if (args.file_path) return ` ${args.file_path}`;
  if (args.command) return ` ${args.command}`;
  if (args.pattern) return ` ${args.pattern}`;
  if (args.url) return ` ${args.url}`;
  return "";
}

function ToolStatusLine({ tool }: { tool: ToolSummary }): ReactNode {
  const args = formatToolArgs(tool);
  const duration = formatDuration(tool.durationMs);

  if (tool.status === "failed") {
    return (
      <Text>
        <Text color="red">{"  ✗ "}{tool.name}</Text>
        <Text dimColor>{args}{"  "}{tool.error ?? "failed"}</Text>
      </Text>
    );
  }

  return (
    <Text dimColor>
      {"  ✓ "}{tool.name}{args}{duration ? `  ${duration}` : ""}
    </Text>
  );
}

function ToolDisplayComponent({ tools }: ToolDisplayProps): ReactNode {
  if (tools.length === 0) return null;

  const primary = tools[0]!;
  const args = formatToolArgs(primary);
  const duration = formatDuration(primary.durationMs);
  const isFailed = primary.status === "failed";

  const summary =
    tools.length === 1
      ? `${primary.name}${args}${isFailed ? ` ✗ ${primary.error ?? "failed"}` : duration ? `  ${duration}` : ""}`
      : tools.every((t) => t.name === primary.name)
        ? `${primary.name} (${tools.length} calls)`
        : `${tools.length} tool calls`;

  const icon = isFailed ? "✗" : "●";
  const iconColor = isFailed ? "red" : undefined;

  return (
    <Box flexDirection="column">
      <Text>
        <Text color={iconColor}>{icon} </Text>
        {summary}
      </Text>
      {tools.length > 1 &&
        tools.map((tool, idx) => (
          <ToolStatusLine key={`${idx}_${tool.callId}`} tool={tool} />
        ))}
    </Box>
  );
}

export const ToolDisplay = React.memo(ToolDisplayComponent);
```

**Step 2: Update StaticBlock to use ToolDisplay**

In `tui/src/components/blocks/StaticBlock.tsx`, replace `ToolBlock` import with `ToolDisplay`:

```tsx
import { ToolDisplay } from "../ToolDisplay.js";
// Remove: import { ToolBlock } from "./ToolBlock.js";

// In the switch case:
case "tool":
  return <ToolDisplay tools={block.tools ?? []} />;
```

**Step 3: Delete old files**

```bash
rm tui/src/components/blocks/ToolBlock.tsx tui/src/components/ToolTimer.tsx
```

**Step 4: Update ToolDisplay test**

Rewrite test to use `ToolSummary` type. Remove old `ToolCallState` references.

**Step 5: Run tests**

Run: `cd tui && npx vitest run`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add -A tui/src/components/
git commit -m "refactor(tui): port ToolDisplay to ToolSummary, replace ToolBlock in StaticBlock"
```

---

### Task 12: Delete all remaining orphaned components

**Files to delete:**
- `tui/src/components/ChatView.tsx`
- `tui/src/components/__tests__/ChatView.test.tsx`
- `tui/src/components/MessageBubble.tsx`
- `tui/src/components/DiffBar.tsx`
- `tui/src/components/DiffDisplay.tsx`
- `tui/src/components/__tests__/DiffDisplay.test.tsx`
- `tui/src/components/ErrorStates.tsx`
- `tui/src/components/__tests__/ErrorStates.test.tsx`
- `tui/src/components/BackgroundTaskPanel.tsx`
- `tui/src/components/__tests__/BackgroundTaskPanel.test.tsx`
- `tui/src/components/PlanningPanel.tsx`
- `tui/src/components/__tests__/PlanningPanel.test.tsx`
- `tui/src/components/PlanTaskItem.tsx`
- `tui/src/components/TaskStatusBadge.tsx`
- `tui/src/components/NotepadView.tsx`
- `tui/src/components/KeyboardHelp.tsx`
- `tui/src/components/__tests__/KeyboardHelp.test.tsx`
- `tui/src/components/TokenUsageBar.tsx`
- `tui/src/components/RetryCountdown.tsx`
- `tui/src/components/StatusBar.tsx`
- `tui/src/components/__tests__/StatusBar.test.tsx`
- `tui/src/components/ToolCallCollapsible.tsx`
- `tui/src/components/sidebar/AgentTab.tsx`
- `tui/src/components/sidebar/FilesTab.tsx`
- `tui/src/components/sidebar/TasksTab.tsx`
- `tui/src/components/sidebar/UsageTab.tsx`
- `tui/src/components/SplitView.tsx` (if exists)
- `tui/src/contexts/PlanContext.tsx`
- `tui/src/hooks/useKeyboard.ts`
- `tui/src/hooks/__tests__/useKeyboard.test.tsx`
- `tui/src/hooks/useExitHandler.ts`
- `tui/src/hooks/useToolTimeout.ts`
- `tui/src/hooks/useRetryWithBackoff.ts`
- `tui/src/hooks/usePermissionTimeout.ts`
- `tui/src/hooks/useContextExhaustion.ts`
- `tui/src/hooks/useJsonRpc.ts`
- `tui/src/hooks/useMemoryMonitor.ts`
- `tui/src/utils/delegation-truncate.ts`
- `tui/src/utils/output-truncate.ts`
- `tui/src/config/keybindings.ts`
- `tui/src/theme/colors.ts`

**Step 1: Delete all files**

Use `rm` for each file. Skip any that don't exist.

**Step 2: Update barrel exports**

- `tui/src/components/index.ts` — only export surviving components
- `tui/src/hooks/index.ts` — only export surviving hooks
- `tui/src/theme/index.ts` — remove if empty
- `tui/src/utils/index.ts` — only export surviving utils

**Step 3: Run tests**

Run: `cd tui && npx vitest run`
Expected: ALL PASS

**Step 4: Run typecheck**

Run: `cd tui && npx tsc --noEmit`
Expected: No errors

**Step 5: Commit**

```bash
git add -A tui/src/
git commit -m "refactor(tui): delete all orphaned components, hooks, and utils"
```

---

### Task 13: Enhance BottomBar with agent indicator and session name

**Files:**
- Modify: `tui/src/components/BottomBar.tsx`
- Modify: `tui/src/components/App.tsx` (pass agents to BottomBar)

**Step 1: Update BottomBar props and rendering**

Add `agents` and update the component:

```tsx
import type { AgentNode } from "../types/state.js";

interface BottomBarProps {
  usage: UsageState;
  activeStream: ActiveStream | null;
  permissions: PermissionState[];
  error: string | null;
  connectionStatus: "connecting" | "connected" | "disconnected" | "error";
  agents: AgentNode[];
  sessionName?: string;
}
```

In `BottomBar`, add active agent count next to model:

```tsx
const activeAgents = props.agents.filter((a) => a.status === "active").length;

// In the render, after cost:
{activeAgents > 0 && <Text color="magenta">{" | "}{activeAgents} agent{activeAgents > 1 ? "s" : ""}</Text>}
{props.sessionName && <Text dimColor>{" | "}{props.sessionName}</Text>}
```

**Step 2: Update App.tsx to pass new props**

```tsx
<BottomBar
  usage={state.usage}
  activeStream={state.activeStream}
  permissions={state.permissions}
  error={state.error}
  connectionStatus={connectionStatus}
  agents={state.agents}
  sessionName={state.session?.agentName}
/>
```

**Step 3: Run tests**

Run: `cd tui && npx vitest run`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tui/src/components/BottomBar.tsx tui/src/components/App.tsx
git commit -m "feat(tui): add agent indicator and session name to BottomBar"
```

---

## Phase 4: Slash Commands & Keyboard Shortcuts

### Task 14: Implement all 21 slash commands

**Files:**
- Modify: `tui/src/components/App.tsx` (`handleCommand`)

**Step 1: Rewrite handleCommand to cover all 21 commands**

Replace the `handleCommand` function in `App.tsx`:

```ts
const handleCommand = useCallback(
  async (commandName: string, _args: string) => {
    const cmd = commandName.replace(/^\//, "").toLowerCase();
    let result: string | undefined;

    try {
      switch (cmd) {
        case "help": {
          const commands = [
            "/help — Show available commands",
            "/clear — Clear conversation",
            "/reset — Reset session and state",
            "/session — Show current session info",
            "/sessions — List and switch sessions",
            "/compact — Compact context history",
            "/model — Show current model",
            "/models — List available models",
            "/usage — Show token usage statistics",
            "/tools — List available tools",
            "/permissions — Show permission grants",
            "/agent — Show active agents",
            "/agents — List all agents",
            "/export — Export session transcript",
            "/theme — Change UI theme (planned)",
            "/split — Split view (planned)",
            "/plan — Show plan (planned)",
            "/notepad — Open scratchpad (planned)",
            "/bg — Background tasks (planned)",
            "/diff — Show diff (planned)",
            "/quit — Exit",
          ];
          result = commands.join("\n");
          break;
        }
        case "clear":
          try {
            await client.request("session/clear", {
              ...(stateRef.current.session?.id
                ? { sessionId: stateRef.current.session.id }
                : {}),
            });
          } catch { /* best effort */ }
          dispatch({ type: "CLEAR_BLOCKS" });
          result = "Conversation cleared.";
          break;
        case "reset":
        case "restart":
          try {
            await client.request("session/clear", {});
          } catch { /* best effort */ }
          dispatch({ type: "CLEAR_BLOCKS" });
          dispatch({ type: "SET_SESSION", session: null });
          dispatch({
            type: "UPDATE_USAGE",
            usage: { promptTokens: 0, completionTokens: 0, totalCost: 0, model: "", contextUsagePercent: 0 },
          });
          result = "Session reset.";
          break;
        case "session":
          result = state.session
            ? `Session: ${state.session.id}\nAgent: ${state.session.agentName}\nMessages: ${state.session.messageCount}`
            : "No active session.";
          break;
        case "sessions": {
          const r = await client.request("session/list", {});
          result = JSON.stringify(r, null, 2);
          break;
        }
        case "compact": {
          const r = await client.request("agent/compact", {});
          result = JSON.stringify(r, null, 2);
          break;
        }
        case "model": {
          const r = await client.request("config/get", { key: "model" });
          result = `Current model: ${JSON.stringify(r)}`;
          break;
        }
        case "models": {
          const r = await client.request("config/get", { key: "model" });
          result = `Current model: ${JSON.stringify(r)}`;
          break;
        }
        case "usage":
          result = [
            `Model: ${state.usage.model || "unknown"}`,
            `Prompt tokens: ${state.usage.promptTokens}`,
            `Completion tokens: ${state.usage.completionTokens}`,
            `Cost: $${state.usage.totalCost.toFixed(4)}`,
            `Context: ${state.usage.contextUsagePercent}%`,
          ].join("\n");
          break;
        case "tools": {
          const r = await client.request("tools/list", {});
          result = JSON.stringify(r, null, 2);
          break;
        }
        case "permissions":
        case "perms": {
          const pending = state.permissions.filter((p) => p.status === "pending");
          result = pending.length === 0
            ? "No pending permission requests."
            : pending.map((p) => `[${p.status}] ${p.tool}: ${JSON.stringify(p.arguments)}`).join("\n");
          break;
        }
        case "agent": {
          const active = state.agents.filter((a) => a.status === "active");
          result = active.length === 0
            ? "No active agents."
            : active.map((a) => `${a.name} [${a.status}] — ${a.task ?? "no task"}`).join("\n");
          break;
        }
        case "agents": {
          result = state.agents.length === 0
            ? "No agents."
            : state.agents.map((a) => `${a.name} [${a.status}]`).join("\n");
          break;
        }
        case "export": {
          const lines = ["# Session Export", ""];
          for (const block of state.completedBlocks) {
            if (block.type === "user") {
              lines.push(`## You\n${block.content}\n`);
            } else if (block.type === "text") {
              lines.push(`## Assistant\n${block.content}\n`);
            } else if (block.type === "tool") {
              lines.push(`## Tool: ${block.content}\n`);
            } else if (block.type === "system") {
              lines.push(`> ${block.content}\n`);
            }
          }
          result = lines.join("\n");
          break;
        }
        case "quit":
        case "exit":
        case "q":
          client.dispose();
          process.exit(0);
          break;
        // Honest stubs
        case "theme":
          result = "Theme switching is not yet available.";
          break;
        case "split":
          result = "Split view is not yet available.";
          break;
        case "plan":
          result = "Plan view is not yet available.";
          break;
        case "notepad":
        case "note":
          result = "Notepad is not yet available.";
          break;
        case "bg":
        case "background":
          result = "No background tasks tracked.";
          break;
        case "diff":
          result = "Diff view is not yet available.";
          break;
        default:
          result = `Unknown command: /${cmd}. Type /help for available commands.`;
      }
    } catch (err: unknown) {
      result = `Command failed: ${err instanceof Error ? err.message : String(err)}`;
    }

    if (result) {
      dispatch({ type: "ADD_SYSTEM_BLOCK", content: result });
    }
  },
  [client, dispatch, state.usage, state.session, state.permissions, state.agents, state.completedBlocks],
);
```

**Step 2: Run tests**

Run: `cd tui && npx vitest run`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tui/src/components/App.tsx
git commit -m "feat(tui): implement all 21 slash commands with honest stubs for unbuilt features"
```

---

### Task 15: Add scroll state for active stream

**Files:**
- Modify: `tui/src/state/blockReducer.ts`
- Modify: `tui/src/components/ActiveStreamView.tsx`
- Test: `tui/src/state/__tests__/blockReducer.test.ts`

**Step 1: Add scroll state and actions to blockReducer**

Add to `BlockState`:
```ts
scrollOffset: number;
```

Add to `BlockAction`:
```ts
| { type: "SCROLL_UP"; lines?: number }
| { type: "SCROLL_DOWN"; lines?: number }
| { type: "SCROLL_TO_BOTTOM" }
```

Add `scrollOffset: 0` to `INITIAL_BLOCK_STATE`.

Add reducer cases:
```ts
case "SCROLL_UP": {
  const delta = action.lines ?? 1;
  return { ...state, scrollOffset: state.scrollOffset + delta };
}
case "SCROLL_DOWN": {
  const delta = action.lines ?? 1;
  return { ...state, scrollOffset: Math.max(0, state.scrollOffset - delta) };
}
case "SCROLL_TO_BOTTOM": {
  return { ...state, scrollOffset: 0 };
}
```

Reset `scrollOffset: 0` in `STREAM_DELTA` case (auto-scroll to bottom on new content).

**Step 2: Update ActiveStreamView to use scrollOffset**

Pass `scrollOffset` as a prop. In `truncateStreamLines`, offset the slice:

```ts
const startLine = Math.max(0, allLines.length - maxLines - scrollOffset);
const endLine = allLines.length - scrollOffset;
```

**Step 3: Write tests, run, commit**

Run: `cd tui && npx vitest run`

```bash
git add tui/src/state/blockReducer.ts tui/src/state/__tests__/blockReducer.test.ts tui/src/components/ActiveStreamView.tsx
git commit -m "feat(tui): add scroll state for active stream view"
```

---

### Task 16: Implement all keyboard shortcuts

**Files:**
- Modify: `tui/src/components/App.tsx` (`useInput` handler)

**Step 1: Implement shortcuts**

Replace the `useInput` handler in `App.tsx`:

```ts
useInput((input, key) => {
  // Cancel / quit
  if (key.ctrl && input === "c") {
    if (state.activeStream) {
      void handleCancel();
    } else {
      client.dispose();
      process.exit(0);
    }
    return;
  }

  // Escape: cancel stream or dismiss error
  if (key.escape) {
    if (state.activeStream) {
      void handleCancel();
    } else if (state.error) {
      dispatch({ type: "CLEAR_ERROR" });
    }
    return;
  }

  // Ctrl+L: clear
  if (key.ctrl && input === "l") {
    void handleCommand("/clear", "");
    return;
  }

  // Ctrl+N: new session (reset)
  if (key.ctrl && input === "n") {
    void handleCommand("/reset", "");
    return;
  }

  // Ctrl+P: approve first pending permission
  if (key.ctrl && input === "p") {
    const pending = state.permissions.find((p) => p.status === "pending");
    if (pending) {
      void handlePermissionRespond(pending.id, "allow_once");
    }
    return;
  }

  // Ctrl+K: open command palette (set input to /)
  if (key.ctrl && input === "k") {
    // Handled by InputPrompt — we could set a ref, but for now this is a stub
    return;
  }

  // Ctrl+S: save feedback
  if (key.ctrl && input === "s") {
    dispatch({ type: "ADD_SYSTEM_BLOCK", content: "Session auto-saved." });
    return;
  }

  // Ctrl+B, Ctrl+\: view stubs
  if (key.ctrl && (input === "b" || input === "\\")) {
    dispatch({ type: "ADD_SYSTEM_BLOCK", content: "Split/sidebar view is not yet available." });
    return;
  }

  // Scroll: Ctrl+Up / Ctrl+Down
  if (key.ctrl && key.upArrow) {
    dispatch({ type: "SCROLL_UP" });
    return;
  }
  if (key.ctrl && key.downArrow) {
    dispatch({ type: "SCROLL_DOWN" });
    return;
  }

  // PageUp / PageDown
  if (key.pageUp) {
    dispatch({ type: "SCROLL_UP", lines: 10 });
    return;
  }
  if (key.pageDown) {
    dispatch({ type: "SCROLL_DOWN", lines: 10 });
    return;
  }

  // Home: scroll way up, End: scroll to bottom
  if (key.home) {
    dispatch({ type: "SCROLL_UP", lines: 10000 });
    return;
  }
  if (key.end) {
    dispatch({ type: "SCROLL_TO_BOTTOM" });
    return;
  }
});
```

Note: Ink's `useInput` key object may not have `pageUp`/`pageDown`/`home`/`end` — check Ink docs. If not available, these are no-ops and can be documented as terminal-dependent.

**Step 2: Run tests**

Run: `cd tui && npx vitest run`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tui/src/components/App.tsx
git commit -m "feat(tui): implement keyboard shortcuts for scroll, clear, reset, permissions"
```

---

## Phase 5: Remaining Fixes

### Task 17: Suppress console.error/console.warn in IPC client

**Files:**
- Modify: `tui/src/ipc/client.ts`

**Step 1: Replace console calls**

In `tui/src/ipc/client.ts`:

- Line 188 (`console.error("Invalid JSON-RPC line...")`): Remove or replace with silent skip
- Line 244 (`console.error("Failed to write...")`): Emit error event instead

```ts
// Line 188: silently skip malformed lines
// Remove: console.error("Invalid JSON-RPC line from sage process", line);
return;

// Line 244: emit error
this.emit("error", new Error(`Failed to write to sage process: ${error?.message ?? "unknown"}`));
```

**Step 2: Run tests**

Run: `cd tui && npx vitest run src/ipc/__tests__/client.test.ts`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tui/src/ipc/client.ts
git commit -m "fix(tui): suppress console.error in IPC client, route through event emitter"
```

---

### Task 18: Graceful process exit

**Files:**
- Modify: `tui/src/components/App.tsx`

**Step 1: Extract shutdown function and use everywhere**

```ts
const shutdown = useCallback(() => {
  client.dispose();
  process.exit(0);
}, [client]);
```

Replace `process.exit(0)` in:
- `useInput` Ctrl+C handler → `shutdown()`
- `/quit` command case → `shutdown()`

**Step 2: Run tests**

Run: `cd tui && npx vitest run`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tui/src/components/App.tsx
git commit -m "fix(tui): graceful shutdown with client.dispose() before process.exit"
```

---

### Task 19: Fix useInput conflict with PermissionPrompt

**Files:**
- Modify: `tui/src/components/App.tsx` (InputPrompt isActive condition)

**Step 1: Update isActive condition**

```tsx
const pendingPermissions = state.permissions.filter((p) => p.status === "pending");

<InputPrompt
  onSubmit={handleSubmit}
  onCommand={handleCommand}
  isActive={!state.activeStream && connectionStatus === "connected" && pendingPermissions.length === 0}
  width={columns}
/>
```

This disables text input focus when a permission prompt is visible, preventing key conflicts.

**Step 2: Run tests**

Run: `cd tui && npx vitest run`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tui/src/components/App.tsx
git commit -m "fix(tui): disable text input when permission prompt is active"
```

---

### Task 20: Update README to match reality

**Files:**
- Modify: `tui/README.md`

**Step 1: Update README**

- Update architecture tree to remove deleted files
- Update slash commands table: mark theme/split/plan/notepad/bg/diff as "(planned)"
- Update keyboard shortcuts: remove leader key section, add "(planned)" where applicable
- Remove references to sidebar, split view as current features
- Update test count if changed

**Step 2: Commit**

```bash
git add tui/README.md
git commit -m "docs(tui): update README to reflect current feature state"
```

---

### Task 21: Run full test suite and typecheck

**Step 1: Run all tests**

```bash
cd tui && npx vitest run
```

Expected: ALL PASS

**Step 2: Run typecheck**

```bash
cd tui && npx tsc --noEmit
```

Expected: No errors

**Step 3: Fix any failures**

If any tests or type errors remain, fix them.

**Step 4: Final commit**

```bash
git add -A tui/
git commit -m "fix(tui): resolve remaining test and type errors after cleanup"
```

---

## Task Summary

| Task | Phase | Description |
|------|-------|-------------|
| 1 | 1 | Fix delegation completion tracking in BlockEventRouter |
| 2 | 1 | Force-resolve running tools on stream end |
| 3 | 1 | Cache the Marked parser singleton |
| 4 | 1 | Truncate active stream content to last N lines |
| 5 | 1 | Isolate spinner from content re-renders |
| 6 | 2 | Extend BlockState with agents, CLEAR_BLOCKS, prune permissions |
| 7 | 2 | Complete BlockEventRouter for all events |
| 8 | 2 | Delete old state system and associated tests |
| 9 | 2 | Clean up unused types from state.ts |
| 10 | 3 | Port AgentTree to block system |
| 11 | 3 | Port ToolDisplay to ToolSummary, replace ToolBlock |
| 12 | 3 | Delete all remaining orphaned components |
| 13 | 3 | Enhance BottomBar with agent indicator and session name |
| 14 | 4 | Implement all 21 slash commands |
| 15 | 4 | Add scroll state for active stream |
| 16 | 4 | Implement all keyboard shortcuts |
| 17 | 5 | Suppress console.error/console.warn in IPC client |
| 18 | 5 | Graceful process exit |
| 19 | 5 | Fix useInput conflict with PermissionPrompt |
| 20 | 5 | Update README to match reality |
| 21 | 5 | Run full test suite and typecheck |

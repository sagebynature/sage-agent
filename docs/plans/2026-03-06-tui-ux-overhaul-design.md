# TUI UX Overhaul: Claude Code-Inspired Redesign

## Problem

The current React/Ink TUI has critical UX gaps:

1. **No markdown rendering** — `MessageBubble` renders raw text. The `MarkdownRenderer` component exists, is tested, works — but is never used in chat.
2. **No scrolling** — `ChatView` uses `overflow="hidden"` with a 50-message window. Earlier messages are inaccessible.
3. **Sidebar is useless** — Three lazy-loaded panels crammed into 30% width with minimal data flow.
4. **Tools disconnected from messages** — Tools tracked globally in `state.tools[]`, not associated with the messages that triggered them.
5. **Cluttered chrome** — Borders, brackets, timestamps, role labels add visual noise without information.

The UX should feel like Claude Code: agent output flows naturally, markdown renders inline, tool calls are compact and contextual, and the terminal's native scroll buffer handles history.

## Design

### Architecture: Static + Dynamic Split

The UI has two zones:

```
STATIC ZONE (terminal scroll buffer via Ink <Static>)
  Completed blocks: user inputs, agent text, tool results, errors
  Written once, then natively scrollable via terminal

DYNAMIC ZONE (Ink live render, bottom of screen)
  Active streaming content (if any)
  ─────────── divider
  > input prompt
  ─────────── divider
  status bar
```

Ink's `<Static items={blocks}>` renders each item once above the live area. Once rendered, items become part of the terminal's scroll buffer — free native scrolling, no viewport constraints, no 50-message limit.

The dynamic zone is small (5-15 lines) and contains only what's actively changing: the current streaming response, input prompt, and status line.

### Visual Language

User messages:
```
> fix the markdown rendering in the TUI
```
- `>` prefix (dimmed)
- Dim text color, no markdown processing
- In the flow so conversations are followable when scrolling back

Agent text output:
```
* Here are the key issues:

  1. **MessageBubble** renders raw text
  2. `ChatView` uses `overflow="hidden"`

  ```typescript
  <Text>{displayContent}</Text>
  ```
```
- `*` prefix
- Full brightness, markdown-rendered via `marked` + `marked-terminal`
- 2-space indent for body content under the bullet

Tool calls (completed):
```
* Read 3 files
  |  tui/src/components/App.tsx
     tui/src/components/ChatView.tsx
     tui/src/renderer/MarkdownRenderer.tsx
```
- `*` prefix with summary line
- `|` connector for sub-items, indented
- Duration shown on summary line for completed tools
- Expandable (future: ctrl+o to show full output)

Tool calls (running):
```
* Read tui/src/components/App.tsx                    ... running
```

Active streaming:
```
~ Thinking... (1m 30s)
```
or when tokens are arriving:
```
* Here is what I found so far:

  The `MessageBubble` component at line 62...
```
- `~` prefix for thinking/waiting state
- `*` prefix once tokens start arriving (same as completed text)
- Live markdown rendering during streaming via `useMarkdownStream` debounce

Errors:
```
* Error: model rate limited, retrying in 5s
```
- `*` prefix, red text

System messages:
```
* Context compaction started: 80% full
```
- `*` prefix, dim italic

Status bar (bottom):
```
model-name | context-bar 42% | $0.15
```
- Single line, compact
- Context bar with color coding (green < 70%, yellow 70-90%, red > 90%)

Input area:
```
──────────────────────────────────────
> type here
──────────────────────────────────────
model-name | context-bar 42% | $0.15
```
- Full-width divider lines above and below
- `>` prompt, minimal
- No border box, no character counter

### State Model

Replace the current `messages: ChatMessage[]` with:

```typescript
interface OutputBlock {
  id: string;
  type: "user" | "text" | "tool" | "error" | "system";
  content: string;
  tools?: ToolSummary[];        // for tool blocks
  timestamp: number;
}

interface ToolSummary {
  name: string;
  callId: string;
  arguments: Record<string, unknown>;
  result?: string;
  error?: string;
  durationMs?: number;
  status: "running" | "completed" | "failed";
}

interface ActiveStream {
  runId: string;
  content: string;              // accumulated markdown text
  tools: ToolSummary[];         // tools in current turn
  isThinking: boolean;          // true before first token
  startedAt: number;
  tokenCount: number;
}
```

State shape:
```typescript
interface AppState {
  completedBlocks: OutputBlock[];    // fed to <Static>
  activeStream: ActiveStream | null; // the live area
  usage: UsageState;
  permissions: PermissionState[];
  error: string | null;
  session: SessionState | null;
}
```

Flow:
1. User submits message -> `OutputBlock { type: "user" }` appended to `completedBlocks`
2. `agent/run` starts -> `activeStream` created with `isThinking: true`
3. `stream/delta` arrives -> `activeStream.content` updated, `isThinking: false`
4. `tool/started` -> tool added to `activeStream.tools` as running
5. `tool/completed` -> tool in `activeStream.tools` updated
6. `run/completed` -> `activeStream` flattened into blocks, appended to `completedBlocks`, `activeStream` set to null

Flattening logic: the active stream becomes multiple blocks:
- Each tool call becomes a `tool` block
- Text content between tool calls becomes `text` blocks
- This preserves the interleaved order of text and tools

### Component Map

| New component | Replaces | Purpose |
|---|---|---|
| `ConversationView` | `ChatView` | `<Static>` wrapper + `ActiveStreamView` |
| `StaticBlock` | `MessageBubble` | Renders one `OutputBlock` by type |
| `TextBlock` | — | `*` + markdown-rendered content |
| `UserBlock` | — | `>` + dim plain text |
| `ToolBlock` | `ToolDisplay` | `*` summary + `\|` sub-items |
| `ActiveStreamView` | `StreamingWaitIndicator` | `~` thinking or `*` live streaming |
| `BottomBar` | `StatusBarHeader` + `StatusBarFooter` | Single status line |
| `InputPrompt` | `InputArea` | `>` prompt between dividers, no borders |

Dropped:
- `MessageBubble` -> `StaticBlock`
- `ChatView` 50-message window -> `<Static>`
- Split view / sidebar -> single pane only
- `StatusBarHeader` / `StatusBarFooter` -> merged `BottomBar`
- Borders around input -> divider lines
- Welcome screen -> simple system message

Reused as-is:
- `MarkdownRenderer` + `CodeBlock` — wired into `TextBlock`
- `PermissionPrompt` — renders in dynamic zone
- `EventRouter` / `wiring.ts` — notification routing unchanged
- `CommandExecutor` / slash commands — input routing unchanged
- `useMarkdownStream` hook — streaming debounce for `ActiveStreamView`

### What's NOT in scope

- Sidebar / split view (can be added later as a toggle)
- Diff display for file edits (future enhancement)
- Tool output expansion (ctrl+o pattern — future)
- Search
- Mouse support
- Theming

### Migration Strategy

This is a rewrite of the view layer only. The integration layer (`EventRouter`, `wiring.ts`, `CommandExecutor`, `SageClient`) stays unchanged. The state model changes from `messages[]` to `completedBlocks[]` + `activeStream`, which means the reducer and EventRouter dispatch logic need updating, but the JSON-RPC protocol layer is untouched.

Build it in this order:
1. New state model + reducer (OutputBlock, ActiveStream)
2. Update EventRouter to dispatch new actions
3. Block renderers (UserBlock, TextBlock, ToolBlock)
4. ConversationView with `<Static>` + ActiveStreamView
5. InputPrompt (simplified)
6. BottomBar (merged status)
7. Wire into AppShell, remove old components
8. Test suite updates

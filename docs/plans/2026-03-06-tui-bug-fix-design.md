# TUI Bug Fix & Cleanup Design

## Problem

The TUI has two critical user-facing bugs and numerous architectural gaps:
1. Delegation/tool activities stuck showing "running" after completion
2. Screen flickering on long responses that overflow terminal height

Root cause: the codebase is mid-migration between two state systems (old `AppState`/`AppContext` vs new `BlockState`/`BlockContext`). The new system is active but incomplete, while the old system's components are orphaned.

## Decisions

- **Commit fully to the block system** — delete old `AppState`/`AppContext`/`EventRouter`
- **Port key components** — `AgentTree`, `ToolDisplay`, `SessionPicker` adapted to block system; delete the rest
- **Implement all 21 documented slash commands** — honest stubs for unwired features
- **Implement all documented keyboard shortcuts** — except leader key sequences (deferred)
- **Truncate active stream** — show last N lines during streaming; full content in `<Static>` on completion

## Phase 1: Core Bug Fixes

### 1a. Delegation completion tracking
- `BlockEventRouter`: store generated `callId` keyed by `params.target` in a `Map<string, string>`
- On `DELEGATION_COMPLETED`: look up callId, dispatch `TOOL_COMPLETED`, then `ADD_SYSTEM_BLOCK`

### 1b. Force-resolve running tools on stream end
- `flattenStream()`: map tool status `"running"` → `"completed"` (or `"cancelled"` if stream cancelled)
- Calculate `durationMs` from tool's creation time to now for tools without proper completion

### 1c. Cache Marked parser
- Module-level singleton in `MarkdownRenderer.tsx`
- `createMarkedRenderer()` returns cached instance on subsequent calls

### 1d. Truncate active stream content
- `StreamContent`: show only last 30 lines during streaming
- Prefix with `"... (streaming, {totalLines} lines)"` when truncated
- Full content rendered via `<Static>` when stream completes

### 1e. Isolate spinner from content re-renders
- Move `SpinnerProvider` to wrap only tool indicators, not stream content
- Extract `StreamContent` outside `SpinnerProvider`

## Phase 2: State System Cleanup

### 2a. Extend BlockState
- Add `agents: AgentNode[]` field
- Add actions: `AGENT_STARTED`, `AGENT_COMPLETED`, `CLEAR_BLOCKS`, `SET_STREAMING`

### 2b. Complete BlockEventRouter
- `DELEGATION_STARTED` → dispatch both `AGENT_STARTED` and `TOOL_STARTED` (with correlation)
- `DELEGATION_COMPLETED` → dispatch both `AGENT_COMPLETED` and `TOOL_COMPLETED`
- Add `METHODS` constants for `LLM_TURN_STARTED`/`LLM_TURN_COMPLETED`, handle in router

### 2c. Delete old state system
- `state/AppContext.tsx`
- `integration/EventRouter.ts`
- `integration/wiring.ts`
- `integration/CommandExecutor.ts`
- `state/selectors.ts`
- Associated test files (unless testing reusable logic)

### 2d. Clean up unused types
- Remove `AppState`, `AppStateV2`, `ChatMessage` from `types/state.ts`
- Keep `ToolCallState`, `AgentNode`, `PermissionState`, `UsageState`, `SessionState`

## Phase 3: Port Key Components

### 3a. AgentTree
- Change `useApp()` → `useBlocks()`, read `state.agents`

### 3b. ToolDisplay / ToolCallCollapsible
- Adapt to accept `ToolSummary` instead of `ToolCallState`
- Replace `ToolBlock` with ported `ToolDisplay` in `StaticBlock`
- Remove `ToolTimer` (completed tools have `durationMs`)

### 3c. SessionPicker
- Change `useApp()` → `useBlocks()` + `useSageClient()`
- Wire into `/sessions` command as interactive picker
- Add modal state to `BlockState`

### 3d. Merge StatusBar into BottomBar
- Add active agent indicator, session name to `BottomBar`

### 3e. Delete orphaned components
- `ChatView.tsx`, `MessageBubble.tsx`, `DiffBar.tsx`, `DiffDisplay.tsx`
- `ErrorStates.tsx`, `BackgroundTaskPanel.tsx`, `PlanningPanel.tsx`, `PlanTaskItem.tsx`
- `TaskStatusBadge.tsx`, `NotepadView.tsx`, `KeyboardHelp.tsx`
- `TokenUsageBar.tsx`, `RetryCountdown.tsx`
- All sidebar tabs

## Phase 4: Slash Commands & Keyboard Shortcuts

### 4a. All 21 slash commands in `handleCommand`
Fully implemented: help, clear, reset, session, sessions, compact, model, models, usage, tools, permissions, agent, agents, export, quit
Honest stubs: theme, split, plan, notepad, bg, diff

### 4b. All keyboard shortcuts in `useInput`
- Navigation: Ctrl+Up/Down (scroll active stream), PageUp/Down, Home/End
- Session: Ctrl+N (new), Ctrl+S (save feedback)
- View: Ctrl+L (clear), Ctrl+B/Ctrl+\ (stubs)
- Agent: Ctrl+P (approve permission), Ctrl+K (command palette)
- Leader keys: deferred

### 4c. Active stream scroll state
- `scrollOffset: number` in BlockState
- `SCROLL_UP`, `SCROLL_DOWN`, `SCROLL_TO_TOP`, `SCROLL_TO_BOTTOM` actions
- Applies to active stream view only (completed blocks use terminal scrollback)

## Phase 5: Remaining Fixes

### 5a. Suppress console.error/console.warn
Route through `SET_ERROR` dispatch or silently skip

### 5b. Graceful process exit
`shutdown()` function: `client.dispose()` then `process.exit(0)`

### 5c. Fix session/clear to pass sessionId

### 5d. Prune permissions on STREAM_END
Remove approved/denied permissions

### 5e. Fix useInput conflicts
Disable text input focus when PermissionPrompt is visible

### 5f. Update README to match reality

### 5g. Update/add tests
- New blockReducer actions
- BlockEventRouter delegation correlation
- Delete tests for removed files
- Command handling and keyboard shortcut tests

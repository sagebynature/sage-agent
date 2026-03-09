# sage-agent TUI

TypeScript terminal UI for sage-agent built with [Ink v6](https://github.com/vadimdemedes/ink) and React 19. Communicates with the Python backend via JSON-RPC over stdio.

## Prerequisites

- Node.js 22+
- pnpm 10+
- Python 3.10+ with sage-agent installed (`pip install -e .` from repo root)

## Install

From the repo root:

```bash
pnpm install
```

## Build

```bash
pnpm --filter tui build
```

Output goes to `tui/dist/`.

To make the CLI available on your `PATH` from the local checkout:

```bash
pnpm --filter tui install:global
```

If `sage-tui` is still not found, run `pnpm setup` once and restart your shell so `PNPM_HOME` is added to `PATH`.

## Run

The TUI spawns `sage serve` as a subprocess. Start the backend first to verify it works:

```bash
# Verify the backend responds to JSON-RPC
echo '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{}}' | sage serve
```

Then launch the TUI:

```bash
# Development (with hot reload via tsx)
pnpm --filter tui dev

# Production (directly)
sage-tui
```

YOLO mode forwards `--yolo` / `-y` to the spawned `sage serve` process, bypassing all backend permission checks:

```bash
# Development
pnpm --filter tui dev -- --yolo

# Production
sage-tui --yolo
sage-tui -y
```

With a specific agent config:

```bash
sage serve --agent-config AGENTS.md
sage serve --agent-config AGENTS.md --yolo
```

## Test

```bash
# Unit + integration tests (~190 tests)
pnpm --filter tui test

# Watch mode
pnpm --filter tui test:watch

# E2E tests (spawns real sage serve subprocess)
pnpm --filter tui test:e2e

# Type check only
pnpm --filter tui typecheck
```

## Slash Commands

Type `/` in the input area to open the command palette. 24 commands available:

| Command | Aliases | Description |
|---------|---------|-------------|
| `/help` | `/h`, `/?` | Show help and available commands |
| `/clear` | `/cls` | Clear conversation |
| `/reset` | `/restart` | Reset session and state |
| `/session` | | Show current session info |
| `/sessions` | | List and switch sessions |
| `/compact` | | Compact context history |
| `/model` | | Show current model |
| `/models` | | List available models |
| `/usage` | | Show token usage statistics |
| `/tools` | | List available tools |
| `/permissions` | `/perms` | Show permission grants |
| `/verbosity` | `/verb` | Set event verbosity level |
| `/events` | | Show or navigate lifecycle events |
| `/filters` | | Filter lifecycle event feed |
| `/agent` | | Show active agents |
| `/agents` | | List all agents |
| `/export` | | Export session transcript |
| `/theme` | | Change UI theme |
| `/split` | | Split view controls |
| `/plan` | | Show or edit current plan |
| `/notepad` | `/note` | Open scratchpad |
| `/bg` | `/background` | Manage background tasks |
| `/diff` | | Show diff of last changes |
| `/quit` | `/exit`, `/q` | Exit the application |

## Keyboard Shortcuts

### Navigation

| Key | Description |
|-----|-------------|
| `PageUp` / `PageDown` | Scroll inspector |
| `Alt+↑` / `Alt+↓` | Previous / next event |

### Session

| Key | Description |
|-----|-------------|
| `Alt+N` | New session (reset) |
| `Alt+L` | Clear conversation |
| `Alt+S` | Save session feedback |
| `Alt+V` | Cycle event verbosity |
| `Alt+E` | Toggle event pane |

### Input

| Key | Description |
|-----|-------------|
| `Enter` | Send message |
| `Ctrl+J` | Insert newline |
| `Ctrl+C` | Cancel stream / quit |
| `Escape` | Cancel stream / dismiss error |
| `↑` / `↓` | Input history |

### Agent

| Key | Description |
|-----|-------------|
| `Alt+P` | Approve pending permission |

## Input Modes

- **`/`** — slash command palette
- **`!`** — inline shell command (e.g. `!git status`)

## Architecture

```
tui/src/
├── index.tsx              # Entry point (Ink render)
├── components/            # React/Ink UI components
│   ├── App.tsx            # Root provider tree + layout
│   ├── ConversationView.tsx # Block-based conversation display
│   ├── InputPrompt.tsx    # Text input with slash command support
│   ├── ActiveStreamView.tsx # Live streaming content + tool indicators
│   ├── BottomBar.tsx      # Status bar (model, cost, cwd, branch, context)
│   ├── ActiveTaskDock.tsx # Persistent active task and streaming indicator dock
│   ├── ComplexityPanel.tsx # Current turn complexity score and contributing factors
│   ├── PermissionPrompt.tsx # Tool permission approval UI
│   ├── ToolDisplay.tsx    # Completed tool summary (ToolSummary-based)
│   ├── EventTimeline.tsx  # Event timeline with verbosity/category filtering
│   ├── EventInspector.tsx # Event detail viewer with correlation IDs
│   ├── PaneFrame.tsx      # Shared bordered container chrome
│   ├── SlashCommands.tsx  # Fuzzy-filtered command overlay
│   ├── SessionPicker.tsx  # Session resume/history
│   ├── AgentTree.tsx      # Delegation hierarchy visualization
│   └── blocks/            # StaticBlock, UserBlock, TextBlock
├── state/                 # BlockContext + blockReducer (block-based state)
├── ipc/                   # SageClient (JSON-RPC over stdio)
├── integration/           # Event processing pipeline
│   ├── EventNormalizer.ts # Normalize raw RPC events to canonical EventRecord
│   ├── EventProjector.ts  # Project EventRecords to block state mutations
│   ├── BlockEventRouter.ts # Route events to block components
│   └── LifecycleManager.ts # Component lifecycle coordination
├── renderer/              # Markdown + syntax-highlighted code blocks
├── hooks/                 # useInputHistory, useResizeHandler, useMessageQueue
├── commands/              # Slash command registry (24 commands)
├── utils/                 # Terminal detection, Unicode fallback, string width
└── types/                 # Protocol, state, blocks, events
```

Communication is JSON-RPC only — zero Python imports in the TUI. The backend runs as a subprocess (`sage serve`) reading/writing newline-delimited JSON-RPC 2.0 on stdin/stdout. All agent lifecycle events are normalized into a canonical `EventRecord` format by the integration layer before reaching UI components, including turn complexity metadata used by `ComplexityPanel` and the active stream UI.

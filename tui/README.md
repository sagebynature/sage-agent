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

With a specific agent config:

```bash
sage serve --agent-config AGENTS.md
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

Type `/` in the input area to open the command palette. 21 commands available:

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
| `/agent` | | Show active agents |
| `/agents` | | List all agents |
| `/export` | | Export session transcript |
| `/theme` | | Change UI theme (planned) |
| `/split` | | Split view (planned) |
| `/plan` | | Show plan (planned) |
| `/notepad` | `/note` | Open scratchpad (planned) |
| `/bg` | `/background` | Background tasks (planned) |
| `/diff` | | Show diff (planned) |
| `/quit` | `/exit`, `/q` | Exit the application |

## Keyboard Shortcuts

### Navigation

| Key | Description |
|-----|-------------|
| `Ctrl+↑` | Scroll up |
| `Ctrl+↓` | Scroll down |

### Session

| Key | Description |
|-----|-------------|
| `Ctrl+N` | New session (reset) |
| `Ctrl+L` | Clear conversation |
| `Ctrl+S` | Save session feedback |

### Input

| Key | Description |
|-----|-------------|
| `Enter` | Send message |
| `Ctrl+C` | Cancel stream / quit |
| `Escape` | Cancel stream / dismiss error |
| `↑` / `↓` | Input history |

### Agent

| Key | Description |
|-----|-------------|
| `Ctrl+P` | Approve pending permission |

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
│   ├── BottomBar.tsx      # Status bar (model, cost, context, agents)
│   ├── PermissionPrompt.tsx # Tool permission approval UI
│   ├── ToolDisplay.tsx    # Completed tool summary (ToolSummary-based)
│   ├── SlashCommands.tsx  # Fuzzy-filtered command overlay
│   ├── SessionPicker.tsx  # Session resume/history
│   ├── AgentTree.tsx      # Delegation hierarchy visualization
│   └── blocks/            # StaticBlock, UserBlock, TextBlock
├── state/                 # BlockContext + blockReducer (block-based state)
├── ipc/                   # SageClient (JSON-RPC over stdio)
├── integration/           # BlockEventRouter, LifecycleManager
├── renderer/              # Markdown + syntax-highlighted code blocks
├── hooks/                 # useInputHistory, useResizeHandler
├── commands/              # Slash command registry (21 commands)
├── utils/                 # Terminal detection, Unicode fallback, string width
└── types/                 # Protocol, state, blocks
```

Communication is JSON-RPC only — zero Python imports in the TUI. The backend runs as a subprocess (`sage serve`) reading/writing newline-delimited JSON-RPC 2.0 on stdin/stdout.

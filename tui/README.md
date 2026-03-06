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

# Production (after build)
node tui/dist/index.js
```

With a specific agent config:

```bash
sage serve --agent-config AGENTS.md
```

## Test

```bash
# Unit + integration tests (342 tests)
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
| `/clear` | `/cls` | Clear screen and scrollback |
| `/reset` | `/restart` | Reset session context and state |
| `/session` | | Manage current session |
| `/sessions` | | List and switch sessions |
| `/compact` | | Toggle compact mode |
| `/model` | | Show or change current model |
| `/models` | | List available models |
| `/usage` | | Show token usage statistics |
| `/tools` | | List available tools |
| `/permissions` | `/perms` | Manage tool permissions |
| `/theme` | | Change UI theme |
| `/split` | | Split view controls |
| `/agent` | | Show current agent status |
| `/agents` | | List available agents |
| `/plan` | | Show or edit current plan |
| `/notepad` | `/note` | Open scratchpad |
| `/bg` | `/background` | Manage background tasks |
| `/diff` | | Show diff of last changes |
| `/export` | | Export session transcript |
| `/quit` | `/exit`, `/q` | Exit the application |

## Keyboard Shortcuts

### Navigation

| Key | Description |
|-----|-------------|
| `Ctrl+↑` | Scroll up |
| `Ctrl+↓` | Scroll down |
| `PageUp` | Page up |
| `PageDown` | Page down |
| `Home` | Scroll to top |
| `End` | Scroll to bottom |

### Session

| Key | Description |
|-----|-------------|
| `Ctrl+N` | New session |
| `Ctrl+Shift+N` | Open session picker |
| `Ctrl+S` | Save current session |

### View

| Key | Description |
|-----|-------------|
| `Ctrl+B` | Toggle sidebar |
| `Ctrl+L` | Clear output |
| `Ctrl+\` | Toggle split view |
| `Ctrl+1..4` | Switch sidebar tabs |

### Input

| Key | Description |
|-----|-------------|
| `Enter` | Send message |
| `Shift+Enter` | Insert newline |
| `Ctrl+C` | Cancel / quit |
| `Ctrl+Z` | Undo |
| `↑` / `↓` | Input history |

### Agent

| Key | Description |
|-----|-------------|
| `Ctrl+P` | Approve pending permission |
| `Ctrl+K` | Open command palette |
| `Ctrl+T` | Show tool list |
| `Ctrl+D` | Dismiss notification |

### Leader Key (`Space` then key)

| Key | Description |
|-----|-------------|
| `?` | Show keyboard help |
| `S` | Save session |
| `K` | Kill background tasks |
| `R` | Restart backend |
| `E` | Export session |
| `Q` | Quit all |

## Input Modes

- **`@`** — file autocomplete (e.g. `@src/index.tsx`)
- **`!`** — inline shell command (e.g. `!git status`)
- **`/`** — slash command palette

## Architecture

```
tui/src/
├── index.tsx              # Entry point (Ink render)
├── components/            # React/Ink UI components
│   ├── App.tsx            # Root provider tree + layout
│   ├── ChatView.tsx       # Message list (virtualized, last 50 visible)
│   ├── InputArea.tsx      # Multi-line input with mode detection
│   ├── StatusBar.tsx      # Header + footer bars (debounced)
│   ├── SplitView.tsx      # 70/30 chat + sidebar layout
│   ├── PermissionPrompt.tsx
│   ├── ToolDisplay.tsx    # 12 tool states (memo'd)
│   ├── DiffDisplay.tsx    # Inline + side-by-side diffs
│   ├── SlashCommands.tsx  # Fuzzy-filtered command overlay
│   ├── ErrorStates.tsx    # Rate limit, context, API key, network, crash
│   ├── SessionPicker.tsx  # Session resume/history
│   ├── AgentTree.tsx      # Delegation hierarchy visualization
│   ├── BackgroundTaskPanel.tsx
│   ├── PlanningPanel.tsx
│   └── KeyboardHelp.tsx
├── state/                 # AppContext (useReducer, 16 action types)
├── ipc/                   # SageClient (JSON-RPC over stdio)
├── integration/           # EventRouter, CommandExecutor, LifecycleManager, wiring
├── renderer/              # Markdown + syntax-highlighted code blocks
├── hooks/                 # useKeyboard, useMarkdownStream, useResizeHandler, etc.
├── commands/              # Slash command registry (21 commands)
├── config/                # Keybindings (30+ shortcuts)
├── utils/                 # Terminal detection, Unicode fallback, string width
└── types/                 # Protocol, state, events, shortcuts
```

Communication is JSON-RPC only — zero Python imports in the TUI. The backend runs as a subprocess (`sage serve`) reading/writing newline-delimited JSON-RPC 2.0 on stdin/stdout.

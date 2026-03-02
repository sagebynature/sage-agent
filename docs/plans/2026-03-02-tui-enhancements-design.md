# TUI Enhancements Design

**Date:** 2026-03-02
**Branch:** 20260226-enhancements

## Overview

Four enhancements to the Sage interactive TUI:

1. Inline tool-call activity in the chat panel (collapsible, like Claude Code)
2. Replace the activity panel with a reactive status panel
3. Log output panel toggled by `ctrl+l`
4. Mouse text selection from chat + message history via arrow keys in the input

---

## Layout

```
┌──────────────────────────────┬──────────────────────┐
│  ChatPanel (65%)             │ StatusPanel (35%)    │
│  VerticalScroll              │ reactive info        │
│    [typed entry widgets]     │                      │
│  HistoryInput                │                      │
└──────────────────────────────┴──────────────────────┘
│  LogPanel (hidden by default, 10 lines, docked bottom) │
└────────────────────────────────────────────────────────┘
│  StatusBar (1 line)                                    │
└────────────────────────────────────────────────────────┘
```

---

## Chat Entry Widgets

The `RichLog` in `ChatPanel` is replaced by a `VerticalScroll` container. Each turn appends typed widgets in order.

### `UserEntry(Widget)`
`Static` with Rich markup. Rendered immediately on submit.

```
You  ╷  what is the capital of france?
```

### `ToolEntry(Widget)`
A `Collapsible` wrapping a `Static`. Collapsed by default, expandable on click.

- **Collapsed:** `▶  bash  ls -la /tmp`
- **Expanded:** shows full input dict and result string

Color by state:
- Yellow — running (no result yet)
- Green — completed successfully
- Red — error

### `ThinkingEntry(Widget)`
Temporary `Static` with animated dots: `◌ Thinking…`
Appended when a turn starts, removed when the first response content arrives.

### `AssistantEntry(Widget)`
`TextArea(read_only=True)` auto-sized to content height. Supports mouse click-to-cursor and click-drag selection. Uses a neutral theme. In streaming mode, chunks are inserted progressively via `insert()`.

### Turn lifecycle

1. User submits → `UserEntry` appended, `ThinkingEntry` appended, input disabled
2. Tool fires → `ToolEntry` appended (yellow, running state)
3. Tool returns → `ToolEntry` updated (green, result populated)
4. Response content arrives → `ThinkingEntry` removed, `AssistantEntry` created
5. Streaming → `AssistantEntry.insert()` called per chunk
6. Turn complete → `AssistantEntry` finalized, input re-enabled

---

## StatusPanel

Replaces `ActivityPanel`. A `VerticalScroll` of reactive `Static` widgets.

### Sections

```
AGENT
  name        sage
  model       claude-opus-4-6
  cwd         ~/projects/myapp
  subagents   coder, reviewer

SKILLS  (3)
  • python-patterns
  • clean-code
  • backend-dev-guidelines

TOKENS  (this turn)
  prompt      12.4k
  completion   1.2k
  cache read   8.1k
  cache write    0

CONTEXT WINDOW
  ████████░░░░░░░  52%  (52k / 100k)

SESSION
  total       45.2k tokens
  cost        $0.0312

ACTIVE AGENTS
  (idle)
```

### Update triggers

- **Mount** — CWD, skills, agent name, model, subagent names (static after this)
- **After each turn** — token/cost/context sections refresh
- **`DelegationStarted`** — ACTIVE AGENTS shows delegatee name + task preview
- **Delegation complete** — ACTIVE AGENTS back to `(idle)`

### Context window bar

Unicode block fill (`█` / `░`), 15 characters wide.
- Green below 60%
- Yellow 60–80%
- Red above 80%

---

## Log Panel

A `RichLog` docked at the bottom, 10 lines tall, hidden by default (`display: none`).

### `TUILogHandler(logging.Handler)`

Installed on the root logger at `on_mount`, removed at `on_unmount`. Posts log records as Textual messages (`LogRecord` message class) to the app, which writes them to the `RichLog`. This keeps log emission thread-safe — no direct widget mutation from the logging thread.

### Format

```
HH:MM:SS  LEVEL    logger.name   message
```

Color by level:
- `DEBUG` — dim
- `INFO` — white
- `WARNING` — yellow
- `ERROR` / `CRITICAL` — red

---

## HistoryInput

`Input` subclass. Maintains `_history: list[str]` and `_history_idx: int`.

- **Up arrow** — if `_history_idx > 0`: decrement, load `_history[_history_idx]`. If at the bottom of history (idx == len), save current value as draft before navigating.
- **Down arrow** — if `_history_idx < len(_history)`: increment. At the end, restore saved draft.
- **Submit** — appends value to `_history`, resets `_history_idx = len(_history)`, clears draft.

---

## Keyboard Bindings

| Key | Action |
|-----|--------|
| `ctrl+q` | Quit |
| `ctrl+l` | Toggle log panel |
| `ctrl+shift+l` + `ctrl+L` | Clear chat (both bound for terminal compat) |
| `ctrl+s` | Toggle stream mode |
| `ctrl+o` | Orchestrate |
| `↑` / `↓` | Message history (handled in `HistoryInput`, not app-level) |

---

## Files Changed

| File | Change |
|------|--------|
| `sage/cli/tui.py` | Full rewrite of `ChatPanel`, new `StatusPanel`, new `LogPanel`, new `HistoryInput`, updated bindings and app lifecycle |

No new files needed beyond the single TUI module.

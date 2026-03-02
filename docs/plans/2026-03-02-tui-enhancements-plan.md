# TUI Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Overhaul the Sage TUI with inline collapsible tool-call activity in chat, a reactive status panel, a toggleable log panel, mouse-selectable agent responses, and arrow-key message history.

**Architecture:** Replace `RichLog` in `ChatPanel` with a `VerticalScroll` of typed entry widgets (`UserEntry`, `ThinkingEntry`, `ToolEntry`, `AssistantEntry`). Replace `ActivityPanel` with a `StatusPanel` of reactive `Static` sections. Add a `LogPanel` (`RichLog` docked at bottom) fed by a custom `logging.Handler`. All changes live in `sage/cli/tui.py`.

**Tech Stack:** Textual >= 0.50 (`Collapsible`, `TextArea`, `VerticalScroll`, `Pilot` for tests), pytest-asyncio (asyncio_mode=auto), Rich markup.

---

## Task 1: HistoryInput widget

**Files:**
- Modify: `sage/cli/tui.py` (add class near top, before `ChatPanel`)
- Create: `tests/test_cli/test_tui.py`

**Step 1: Create test file with failing test**

```python
# tests/test_cli/test_tui.py
"""Tests for TUI widgets."""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from sage.cli.tui import HistoryInput


class _HistoryApp(App[None]):
    def compose(self) -> ComposeResult:
        yield HistoryInput(id="inp")


async def test_history_input_up_navigates_to_last_entry() -> None:
    app = _HistoryApp()
    async with app.run_test() as pilot:
        inp = app.query_one(HistoryInput)
        inp.append_history("first")
        inp.append_history("second")
        await pilot.press("up")
        assert inp.value == "second"


async def test_history_input_up_twice() -> None:
    app = _HistoryApp()
    async with app.run_test() as pilot:
        inp = app.query_one(HistoryInput)
        inp.append_history("first")
        inp.append_history("second")
        await pilot.press("up")
        await pilot.press("up")
        assert inp.value == "first"


async def test_history_input_down_restores_draft() -> None:
    app = _HistoryApp()
    async with app.run_test() as pilot:
        inp = app.query_one(HistoryInput)
        inp.append_history("first")
        await pilot.click("#inp")
        await pilot.type("draft text")
        await pilot.press("up")
        assert inp.value == "first"
        await pilot.press("down")
        assert inp.value == "draft text"


async def test_history_up_at_top_does_not_go_further() -> None:
    app = _HistoryApp()
    async with app.run_test() as pilot:
        inp = app.query_one(HistoryInput)
        inp.append_history("only")
        await pilot.press("up")
        await pilot.press("up")   # should not crash, stays at "only"
        assert inp.value == "only"


async def test_history_down_at_bottom_is_noop() -> None:
    app = _HistoryApp()
    async with app.run_test() as pilot:
        inp = app.query_one(HistoryInput)
        await pilot.press("down")  # empty history, no crash
        assert inp.value == ""
```

**Step 2: Run to confirm failures**

```bash
pytest tests/test_cli/test_tui.py -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name 'HistoryInput'`

**Step 3: Implement HistoryInput in `sage/cli/tui.py`**

Add this class after the `_fmt_args` helper (~line 179) and before `ChatPanel`:

```python
# ── HistoryInput ──────────────────────────────────────────────────────────────


class HistoryInput(Input):
    """Input widget with up/down arrow message history, like a shell prompt."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._history: list[str] = []
        self._history_idx: int = 0
        self._draft: str = ""

    def append_history(self, value: str) -> None:
        """Add a submitted message to history and reset cursor to end."""
        if value:
            self._history.append(value)
        self._history_idx = len(self._history)
        self._draft = ""

    def _on_key(self, event: events.Key) -> None:
        if event.key == "up":
            if self._history_idx > 0:
                if self._history_idx == len(self._history):
                    self._draft = self.value
                self._history_idx -= 1
                self.value = self._history[self._history_idx]
                self.cursor_position = len(self.value)
                event.prevent_default()
                event.stop()
        elif event.key == "down":
            if self._history_idx < len(self._history):
                self._history_idx += 1
                if self._history_idx == len(self._history):
                    self.value = self._draft
                else:
                    self.value = self._history[self._history_idx]
                self.cursor_position = len(self.value)
                event.prevent_default()
                event.stop()
```

Also add `from textual import events` to the imports at the top of `tui.py`.

**Step 4: Run tests**

```bash
pytest tests/test_cli/test_tui.py -v
```

Expected: all 5 pass.

**Step 5: Commit**

```bash
git add sage/cli/tui.py tests/test_cli/test_tui.py
git commit -m "feat(tui): add HistoryInput with up/down arrow navigation"
```

---

## Task 2: UserEntry and ThinkingEntry widgets

**Files:**
- Modify: `sage/cli/tui.py`
- Modify: `tests/test_cli/test_tui.py`

**Step 1: Add tests**

```python
# append to tests/test_cli/test_tui.py
from sage.cli.tui import UserEntry, ThinkingEntry


async def test_user_entry_renders_message() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield UserEntry("hello world")

    app = _App()
    async with app.run_test():
        widget = app.query_one(UserEntry)
        # Widget exists and is mounted
        assert widget is not None


async def test_thinking_entry_is_mounted() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield ThinkingEntry()

    app = _App()
    async with app.run_test():
        widget = app.query_one(ThinkingEntry)
        assert widget is not None
```

**Step 2: Run to confirm failure**

```bash
pytest tests/test_cli/test_tui.py::test_user_entry_renders_message -v
```

Expected: `ImportError`

**Step 3: Implement both widgets in `sage/cli/tui.py`**

Add after `HistoryInput`, before `ChatPanel`:

```python
# ── Chat entry widgets ────────────────────────────────────────────────────────


class UserEntry(Widget):
    """A single user message in the chat scroll view."""

    DEFAULT_CSS = """
    UserEntry {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }
    """

    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text

    def compose(self) -> ComposeResult:
        yield Static(f"[bold cyan]You[/bold cyan]  [dim]╷[/dim]  {self._text}")


class ThinkingEntry(Widget):
    """Animated 'thinking' indicator, removed when the response starts."""

    DEFAULT_CSS = """
    ThinkingEntry {
        height: 1;
        padding: 0 1;
        margin-bottom: 1;
    }
    """

    _FRAMES = ["◌", "◎", "●", "◎"]

    def compose(self) -> ComposeResult:
        yield Static("[dim]◌ Thinking…[/dim]", id="thinking-label")

    def on_mount(self) -> None:
        self._frame = 0
        self.set_interval(0.25, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(self._FRAMES)
        self.query_one("#thinking-label", Static).update(
            f"[dim]{self._FRAMES[self._frame]} Thinking…[/dim]"
        )
```

**Step 4: Run tests**

```bash
pytest tests/test_cli/test_tui.py -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add sage/cli/tui.py tests/test_cli/test_tui.py
git commit -m "feat(tui): add UserEntry and ThinkingEntry chat widgets"
```

---

## Task 3: ToolEntry widget

**Files:**
- Modify: `sage/cli/tui.py`
- Modify: `tests/test_cli/test_tui.py`

**Step 1: Add tests**

```python
# append to tests/test_cli/test_tui.py
from sage.cli.tui import ToolEntry
from textual.widgets import Collapsible


async def test_tool_entry_starts_collapsed() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield ToolEntry("bash", {"command": "ls"})

    app = _App()
    async with app.run_test():
        c = app.query_one(Collapsible)
        assert c.collapsed is True


async def test_tool_entry_set_result_updates_widget() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield ToolEntry("bash", {"command": "ls"})

    app = _App()
    async with app.run_test():
        entry = app.query_one(ToolEntry)
        entry.set_result("file1\nfile2")
        # No crash, widget updated
        assert entry._result == "file1\nfile2"
        assert entry._error is False


async def test_tool_entry_set_error_marks_error() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield ToolEntry("bash", {"command": "bad"})

    app = _App()
    async with app.run_test():
        entry = app.query_one(ToolEntry)
        entry.set_result("command not found", error=True)
        assert entry._error is True
```

**Step 2: Run to confirm failure**

```bash
pytest tests/test_cli/test_tui.py::test_tool_entry_starts_collapsed -v
```

Expected: `ImportError`

**Step 3: Implement ToolEntry in `sage/cli/tui.py`**

Add after `ThinkingEntry`:

```python
class ToolEntry(Widget):
    """A tool call rendered as a collapsible block. Yellow while running, green/red when done."""

    DEFAULT_CSS = """
    ToolEntry {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }
    ToolEntry Collapsible {
        height: auto;
        border: none;
        padding: 0;
        margin: 0;
    }
    """

    def __init__(self, tool_name: str, arguments: dict[str, Any]) -> None:
        super().__init__()
        self._tool_name = tool_name
        self._arguments = arguments
        self._result: str | None = None
        self._error: bool = False

    def _summary(self, icon: str = "▶", color: str = "yellow") -> str:
        args_str = _fmt_args(self._arguments)
        return f"[{color}]{icon}[/{color}]  [bold]{self._tool_name}[/bold]  [dim]{args_str}[/dim]"

    def compose(self) -> ComposeResult:
        with Collapsible(title=self._summary(), collapsed=True):
            yield Static(f"[dim]input:[/dim]   {self._arguments}", id="tool-input")
            yield Static("[dim]result:[/dim]  [dim]running…[/dim]", id="tool-result")

    def set_result(self, result: str, error: bool = False) -> None:
        """Update the entry once the tool has completed."""
        self._result = result
        self._error = error
        color = "red" if error else "green"
        icon = "✗" if error else "✓"
        preview = result[:300] + "…" if len(result) > 300 else result
        self.query_one(Collapsible).title = self._summary(icon=icon, color=color)
        self.query_one("#tool-result", Static).update(
            f"[dim]result:[/dim]  [{color}]{preview}[/{color}]"
        )
```

Also add `from textual.widgets import ..., Collapsible` to the existing import line.

**Step 4: Run tests**

```bash
pytest tests/test_cli/test_tui.py -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add sage/cli/tui.py tests/test_cli/test_tui.py
git commit -m "feat(tui): add ToolEntry collapsible widget for tool calls"
```

---

## Task 4: AssistantEntry widget

**Files:**
- Modify: `sage/cli/tui.py`
- Modify: `tests/test_cli/test_tui.py`

**Step 1: Add tests**

```python
# append to tests/test_cli/test_tui.py
from sage.cli.tui import AssistantEntry
from textual.widgets import TextArea


async def test_assistant_entry_initial_text() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield AssistantEntry()

    app = _App()
    async with app.run_test():
        ta = app.query_one(TextArea)
        assert ta.read_only is True


async def test_assistant_entry_append_text() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield AssistantEntry()

    app = _App()
    async with app.run_test():
        entry = app.query_one(AssistantEntry)
        entry.append_chunk("hello ")
        entry.append_chunk("world")
        ta = app.query_one(TextArea)
        assert "hello world" in ta.text
```

**Step 2: Run to confirm failure**

```bash
pytest tests/test_cli/test_tui.py::test_assistant_entry_initial_text -v
```

Expected: `ImportError`

**Step 3: Implement AssistantEntry in `sage/cli/tui.py`**

Add after `ToolEntry`:

```python
class AssistantEntry(Widget):
    """Agent response rendered in a read-only TextArea supporting mouse selection."""

    DEFAULT_CSS = """
    AssistantEntry {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }
    AssistantEntry .assistant-label {
        color: $success;
        text-style: bold;
    }
    AssistantEntry TextArea {
        height: auto;
        min-height: 1;
        border: none;
        padding: 0;
        background: transparent;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._content = ""

    def compose(self) -> ComposeResult:
        yield Static("[bold green]Agent[/bold green]  [dim]╷[/dim]", classes="assistant-label")
        yield TextArea("", read_only=True, show_line_numbers=False, id="response-area")

    def append_chunk(self, chunk: str) -> None:
        """Append a streaming text chunk."""
        self._content += chunk
        ta = self.query_one("#response-area", TextArea)
        # Insert at end of document
        end = ta.document.end
        ta.insert(chunk, location=end)
        self._sync_height()

    def set_text(self, text: str) -> None:
        """Replace full text (used in non-streaming mode)."""
        self._content = text
        ta = self.query_one("#response-area", TextArea)
        ta.load_text(text)
        self._sync_height()

    def _sync_height(self) -> None:
        """Resize TextArea to fit content (no internal scrollbar)."""
        lines = max(1, self._content.count("\n") + 1)
        self.query_one("#response-area", TextArea).styles.height = lines
```

**Step 4: Run tests**

```bash
pytest tests/test_cli/test_tui.py -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add sage/cli/tui.py tests/test_cli/test_tui.py
git commit -m "feat(tui): add AssistantEntry with TextArea for mouse-selectable responses"
```

---

## Task 5: ChatPanel refactor

**Files:**
- Modify: `sage/cli/tui.py` — replace `ChatPanel` body
- Modify: `tests/test_cli/test_tui.py`

**Step 1: Add tests**

```python
# append to tests/test_cli/test_tui.py
from sage.cli.tui import ChatPanel
from textual.widgets import VerticalScroll


async def test_chat_panel_append_user_message() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield ChatPanel(id="chat")

    app = _App()
    async with app.run_test():
        panel = app.query_one(ChatPanel)
        panel.append_user_message("test message")
        assert len(app.query(UserEntry)) == 1


async def test_chat_panel_start_and_finish_turn() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield ChatPanel(id="chat")

    app = _App()
    async with app.run_test():
        panel = app.query_one(ChatPanel)
        panel.start_turn()
        assert len(app.query(ThinkingEntry)) == 1
        entry = panel.start_response()
        # ThinkingEntry removed, AssistantEntry added
        assert len(app.query(ThinkingEntry)) == 0
        assert len(app.query(AssistantEntry)) == 1


async def test_chat_panel_add_tool_call() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield ChatPanel(id="chat")

    app = _App()
    async with app.run_test():
        panel = app.query_one(ChatPanel)
        tool = panel.add_tool_call("bash", {"command": "ls"})
        assert isinstance(tool, ToolEntry)
        assert len(app.query(ToolEntry)) == 1


async def test_chat_panel_clear() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield ChatPanel(id="chat")

    app = _App()
    async with app.run_test():
        panel = app.query_one(ChatPanel)
        panel.append_user_message("hi")
        panel.clear_entries()
        assert len(app.query(UserEntry)) == 0
```

**Step 2: Run to confirm failures**

```bash
pytest tests/test_cli/test_tui.py::test_chat_panel_append_user_message -v
```

Expected: tests fail (ChatPanel missing new API methods)

**Step 3: Rewrite ChatPanel in `sage/cli/tui.py`**

Replace the existing `ChatPanel` class entirely:

```python
class ChatPanel(Widget):
    """Left panel: conversation history (typed entry widgets) and message input."""

    DEFAULT_CSS = """
    ChatPanel {
        width: 65%;
        height: 100%;
        border-right: solid $primary;
    }
    ChatPanel #chat-label {
        padding: 0 1;
        color: $text-muted;
        text-style: bold;
    }
    ChatPanel #chat-scroll {
        height: 1fr;
    }
    ChatPanel HistoryInput {
        dock: bottom;
        margin: 0 1 1 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("CHAT", id="chat-label")
        yield VerticalScroll(id="chat-scroll")
        yield HistoryInput(placeholder="> Type a message and press Enter…", id="chat-input")

    # -- Public API used by SageTUIApp ----------------------------------------

    def append_user_message(self, text: str) -> None:
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.mount(UserEntry(text))
        scroll.scroll_end(animate=False)

    def start_turn(self) -> None:
        """Show the animated thinking indicator."""
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.mount(ThinkingEntry(id="thinking"))
        scroll.scroll_end(animate=False)

    def add_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> ToolEntry:
        """Append a ToolEntry (yellow/running) and return it for later update."""
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        entry = ToolEntry(tool_name, arguments)
        # Remove thinking entry if still present — first tool call replaces it
        thinking = self.query("#thinking")
        if thinking:
            thinking.first().remove()
        scroll.mount(entry)
        scroll.scroll_end(animate=False)
        return entry

    def start_response(self) -> AssistantEntry:
        """Remove thinking indicator, append AssistantEntry, return it."""
        thinking = self.query("#thinking")
        if thinking:
            thinking.first().remove()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        entry = AssistantEntry()
        scroll.mount(entry)
        scroll.scroll_end(animate=False)
        return entry

    def clear_entries(self) -> None:
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.remove_children()
```

Also update the `VerticalScroll` import in the imports:
```python
from textual.containers import Horizontal, Vertical, VerticalScroll
```

**Step 4: Run tests**

```bash
pytest tests/test_cli/test_tui.py -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add sage/cli/tui.py tests/test_cli/test_tui.py
git commit -m "feat(tui): refactor ChatPanel to use typed entry widgets"
```

---

## Task 6: StatusPanel

**Files:**
- Modify: `sage/cli/tui.py` — add StatusPanel, remove ActivityPanel
- Modify: `tests/test_cli/test_tui.py`

**Step 1: Add tests**

```python
# append to tests/test_cli/test_tui.py
from sage.cli.tui import StatusPanel
from unittest.mock import MagicMock


def _make_mock_agent(
    name: str = "test",
    model: str = "gpt-4o",
    skills: list | None = None,
    subagents: dict | None = None,
) -> MagicMock:
    agent = MagicMock()
    agent.name = name
    agent.model = model
    agent.skills = skills or []
    agent.subagents = subagents or {}
    return agent


async def test_status_panel_initializes() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield StatusPanel(id="status")

    app = _App()
    async with app.run_test():
        panel = app.query_one(StatusPanel)
        agent = _make_mock_agent()
        panel.initialize(agent)  # no crash


async def test_status_panel_update_tokens_no_crash() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield StatusPanel(id="status")

    app = _App()
    async with app.run_test():
        panel = app.query_one(StatusPanel)
        panel.initialize(_make_mock_agent())
        stats = {
            "token_usage": 5000,
            "context_window_limit": 100000,
            "cumulative_prompt_tokens": 4000,
            "cumulative_completion_tokens": 1000,
            "cumulative_cache_read_tokens": 500,
            "cumulative_cache_creation_tokens": 100,
            "cumulative_reasoning_tokens": 0,
            "cumulative_total_tokens": 5000,
            "cumulative_cost": 0.012,
        }
        panel.update_stats(stats)  # no crash


async def test_status_panel_active_agents_delegation() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield StatusPanel(id="status")

    app = _App()
    async with app.run_test():
        panel = app.query_one(StatusPanel)
        panel.initialize(_make_mock_agent())
        panel.set_active_delegation("coder", "write a function")
        panel.clear_active_delegation()  # no crash
```

**Step 2: Run to confirm failure**

```bash
pytest tests/test_cli/test_tui.py::test_status_panel_initializes -v
```

Expected: `ImportError`

**Step 3: Implement StatusPanel in `sage/cli/tui.py`**

Delete the `ActivityPanel` class entirely. Add `StatusPanel` in its place:

```python
class StatusPanel(Widget):
    """Right panel: static agent info + live token/cost/context stats."""

    DEFAULT_CSS = """
    StatusPanel {
        width: 35%;
        height: 100%;
        overflow-y: auto;
        padding: 1;
    }
    StatusPanel .section {
        height: auto;
        margin-bottom: 1;
        padding-bottom: 1;
        border-bottom: solid $primary-darken-3;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="agent-section", classes="section")
        yield Static("", id="skills-section", classes="section")
        yield Static("", id="tokens-section", classes="section")
        yield Static("", id="context-section", classes="section")
        yield Static("", id="session-section", classes="section")
        yield Static("", id="active-section")

    def initialize(self, agent: "Agent") -> None:
        """Populate static sections from agent config. Call once after mount."""
        import os

        cwd = os.getcwd()
        subagent_names = ", ".join(agent.subagents.keys()) or "[dim](none)[/dim]"
        self.query_one("#agent-section", Static).update(
            f"[bold]AGENT[/bold]\n"
            f"  [dim]name[/dim]       {agent.name}\n"
            f"  [dim]model[/dim]      {agent.model}\n"
            f"  [dim]cwd[/dim]        {cwd}\n"
            f"  [dim]subagents[/dim]  {subagent_names}"
        )
        skill_names = [s.name for s in agent.skills]
        if skill_names:
            skills_text = f"[bold]SKILLS[/bold]  ({len(skill_names)})\n"
            skills_text += "\n".join(f"  [dim]•[/dim] {n}" for n in skill_names)
        else:
            skills_text = "[bold]SKILLS[/bold]\n  [dim](none)[/dim]"
        self.query_one("#skills-section", Static).update(skills_text)
        # Render zeros for tokens/session until first turn
        self.update_stats({})
        self.clear_active_delegation()

    def update_stats(self, stats: dict[str, Any]) -> None:
        """Refresh token, context window, and session sections."""
        prompt = int(stats.get("cumulative_prompt_tokens") or 0)
        completion = int(stats.get("cumulative_completion_tokens") or 0)
        cache_read = int(stats.get("cumulative_cache_read_tokens") or 0)
        cache_write = int(stats.get("cumulative_cache_creation_tokens") or 0)
        reasoning = int(stats.get("cumulative_reasoning_tokens") or 0)

        tokens_lines = [
            "[bold]TOKENS[/bold]",
            f"  [dim]prompt[/dim]      {format_tokens(prompt)}",
            f"  [dim]completion[/dim]  {format_tokens(completion)}",
            f"  [dim]cache read[/dim]  {format_tokens(cache_read)}",
            f"  [dim]cache write[/dim] {format_tokens(cache_write)}",
        ]
        if reasoning:
            tokens_lines.append(f"  [dim]reasoning[/dim]  {format_tokens(reasoning)}")
        self.query_one("#tokens-section", Static).update("\n".join(tokens_lines))

        token_usage = int(stats.get("token_usage") or 0)
        limit = int(stats.get("context_window_limit") or 0)
        if limit > 0:
            ratio = min(1.0, token_usage / limit)
            filled = int(ratio * 15)
            bar = "█" * filled + "░" * (15 - filled)
            pct = int(ratio * 100)
            color = "red" if ratio >= 0.8 else ("yellow" if ratio >= 0.6 else "green")
            context_text = (
                f"[bold]CONTEXT WINDOW[/bold]\n"
                f"  [{color}]{bar}[/{color}]  {pct}%\n"
                f"  [dim]({format_tokens(token_usage)} / {format_tokens(limit)})[/dim]"
            )
        else:
            context_text = "[bold]CONTEXT WINDOW[/bold]\n  [dim](unknown)[/dim]"
        self.query_one("#context-section", Static).update(context_text)

        total = int(stats.get("cumulative_total_tokens") or 0)
        cost = float(stats.get("cumulative_cost") or 0.0)
        self.query_one("#session-section", Static).update(
            f"[bold]SESSION[/bold]\n"
            f"  [dim]total[/dim]  {format_tokens(total)} tokens\n"
            f"  [dim]cost[/dim]   [green]${cost:.4f}[/green]"
        )

    def set_active_delegation(self, target: str, task: str) -> None:
        preview = task[:45] + "…" if len(task) > 45 else task
        self.query_one("#active-section", Static).update(
            f"[bold]ACTIVE AGENTS[/bold]\n"
            f"  [yellow]↳[/yellow] {target}  [dim]{preview!r}[/dim]"
        )

    def clear_active_delegation(self) -> None:
        self.query_one("#active-section", Static).update(
            "[bold]ACTIVE AGENTS[/bold]\n  [dim](idle)[/dim]"
        )
```

**Step 4: Run tests**

```bash
pytest tests/test_cli/test_tui.py -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add sage/cli/tui.py tests/test_cli/test_tui.py
git commit -m "feat(tui): add StatusPanel replacing ActivityPanel"
```

---

## Task 7: LogPanel + TUILogHandler

**Files:**
- Modify: `sage/cli/tui.py`
- Modify: `tests/test_cli/test_tui.py`

**Step 1: Add tests**

```python
# append to tests/test_cli/test_tui.py
import logging
from sage.cli.tui import LogPanel, TUILogHandler, _LogRecord


async def test_log_panel_starts_hidden() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield LogPanel(id="logs")

    app = _App()
    async with app.run_test():
        panel = app.query_one(LogPanel)
        assert panel.display is False


async def test_log_panel_toggle_shows_and_hides() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield LogPanel(id="logs")

    app = _App()
    async with app.run_test():
        panel = app.query_one(LogPanel)
        panel.toggle_visibility()
        assert panel.display is True
        panel.toggle_visibility()
        assert panel.display is False


def test_tui_log_handler_emit_does_not_raise() -> None:
    """Handler must not raise even when the app reference is a mock."""
    from unittest.mock import MagicMock

    mock_app = MagicMock()
    handler = TUILogHandler(mock_app)
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None
    )
    handler.emit(record)
    mock_app.post_message.assert_called_once()
```

**Step 2: Run to confirm failure**

```bash
pytest tests/test_cli/test_tui.py::test_log_panel_starts_hidden -v
```

Expected: `ImportError`

**Step 3: Implement LogPanel, TUILogHandler, _LogRecord in `sage/cli/tui.py`**

Add after `StatusPanel` and before `OrchestrationScreen`:

```python
# ── Log panel ────────────────────────────────────────────────────────────────


class _LogRecord(Message):
    """Carries a logging.LogRecord across thread boundaries into the Textual loop."""

    def __init__(self, record: logging.LogRecord) -> None:
        super().__init__()
        self.record = record


class TUILogHandler(logging.Handler):
    """Logging handler that forwards records to the TUI via post_message."""

    def __init__(self, app: App[None]) -> None:
        super().__init__()
        self._app = app

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._app.post_message(_LogRecord(record))
        except Exception:
            pass  # Never let logging raise


_LOG_COLORS = {
    logging.DEBUG: "dim",
    logging.INFO: "white",
    logging.WARNING: "yellow",
    logging.ERROR: "red",
    logging.CRITICAL: "bold red",
}
_LOG_FMT = logging.Formatter(
    "%(asctime)s.%(msecs)03d  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)


class LogPanel(Widget):
    """Docked-bottom log viewer, hidden by default. Toggle with ctrl+l."""

    DEFAULT_CSS = """
    LogPanel {
        dock: bottom;
        height: 10;
        border-top: solid $primary-darken-2;
        display: none;
    }
    LogPanel #log-label {
        padding: 0 1;
        color: $text-muted;
        text-style: bold;
    }
    LogPanel #log-output {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("LOGS", id="log-label")
        yield RichLog(id="log-output", wrap=True, markup=True, highlight=False)

    def toggle_visibility(self) -> None:
        self.display = not self.display

    def write_record(self, record: logging.LogRecord) -> None:
        color = _LOG_COLORS.get(record.levelno, "white")
        msg = _LOG_FMT.format(record)
        # Escape Rich markup characters in the raw message to prevent injection
        safe_msg = msg.replace("[", "\\[")
        self.query_one("#log-output", RichLog).write(f"[{color}]{safe_msg}[/{color}]")
```

Also add `import logging` at the top of `tui.py`.

**Step 4: Run tests**

```bash
pytest tests/test_cli/test_tui.py -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add sage/cli/tui.py tests/test_cli/test_tui.py
git commit -m "feat(tui): add LogPanel and TUILogHandler for togglable log output"
```

---

## Task 8: Wire SageTUIApp

**Files:**
- Modify: `sage/cli/tui.py` — rewrite `SageTUIApp`

This task integrates all the new pieces. There are no new tests here — existing unit tests cover the widgets; we rely on them. The main integration test is: app starts without crashing, ctrl+q exits.

**Step 1: Add integration test**

```python
# append to tests/test_cli/test_tui.py
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


def _make_config_path(tmp_path: Path) -> Path:
    cfg = tmp_path / "AGENTS.md"
    cfg.write_text(
        "---\nname: test-agent\nmodel: gpt-4o\n---\nA helpful assistant.\n"
    )
    return cfg


async def test_sage_tui_app_mounts_and_quits(tmp_path: Path) -> None:
    from sage.cli.tui import SageTUIApp

    cfg = _make_config_path(tmp_path)
    mock_agent = _make_mock_agent()
    mock_agent.skills = []
    mock_agent.subagents = {}
    mock_agent.close = AsyncMock()

    with patch("sage.cli.tui.Agent.from_config", return_value=mock_agent):
        app = SageTUIApp(config_path=cfg)
        async with app.run_test() as pilot:
            # App mounted without error
            assert app.query_one(ChatPanel) is not None
            assert app.query_one(StatusPanel) is not None
            assert app.query_one(LogPanel) is not None
            await pilot.press("ctrl+q")
        # on_unmount called agent.close
        mock_agent.close.assert_awaited_once()
```

**Step 2: Run to confirm current state**

```bash
pytest tests/test_cli/test_tui.py::test_sage_tui_app_mounts_and_quits -v
```

May fail due to missing StatusPanel/ChatPanel methods being called. That's expected.

**Step 3: Rewrite `SageTUIApp` in `sage/cli/tui.py`**

Replace the existing `SageTUIApp` class entirely:

```python
class SageTUIApp(App[None]):
    """Interactive split-screen TUI for a Sage agent config."""

    CSS = """
    #main-layout {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+l", "toggle_logs", "Logs"),
        Binding("ctrl+shift+l", "clear_chat", "Clear"),
        Binding("ctrl+L", "clear_chat", "Clear", show=False),  # terminal compat
        Binding("ctrl+o", "orchestrate", "Orchestrate"),
        Binding("ctrl+s", "toggle_stream", "Toggle stream"),
    ]

    TITLE = "Sage TUI"

    def __init__(self, config_path: Path, central: "MainConfig | None" = None) -> None:
        super().__init__()
        self.config_path = config_path
        self._central = central
        self._agent: Agent | None = None
        self._streaming_mode: bool = True
        # Tracks the active AssistantEntry being streamed into
        self._current_response: AssistantEntry | None = None
        # Maps tool_name -> queue of ToolEntry widgets (handles parallel calls)
        self._pending_tools: dict[str, list[ToolEntry]] = {}
        # Log handler installed at mount, removed at unmount
        self._log_handler: TUILogHandler | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            yield ChatPanel(id="chat-panel")
            yield StatusPanel(id="status-panel")
        yield LogPanel(id="log-panel")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        # Install log handler
        self._log_handler = TUILogHandler(self)
        self._log_handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(self._log_handler)

        # Build agent
        agent = Agent.from_config(self.config_path, central=self._central)
        self._agent = agent
        instrument_agent(agent, self)

        # Initialise panels
        self.query_one(StatusPanel).initialize(agent)
        self.query_one(StatusBar).set_state(
            "Ready", agent.name, agent.model,
            has_subagents=bool(agent.subagents),
            streaming_mode=self._streaming_mode,
        )
        self.sub_title = f"{agent.name} ({agent.model})"
        self.query_one("#chat-input", HistoryInput).focus()

    async def on_unmount(self) -> None:
        if self._log_handler is not None:
            logging.getLogger().removeHandler(self._log_handler)
        if self._agent is not None:
            await self._agent.close()

    # ── Log record handler ────────────────────────────────────────────────────

    def on__log_record(self, event: _LogRecord) -> None:
        self.query_one(LogPanel).write_record(event.record)

    # ── Input handling ────────────────────────────────────────────────────────

    @on(Input.Submitted, "#chat-input")
    def handle_chat_input(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query or self._agent is None:
            return
        input_widget = self.query_one("#chat-input", HistoryInput)
        input_widget.append_history(query)
        input_widget.clear()
        input_widget.disabled = True

        chat = self.query_one(ChatPanel)
        chat.append_user_message(query)
        chat.start_turn()

        agent = self._agent
        self._pending_tools.clear()
        self._current_response = None

        if self._streaming_mode:
            self.query_one(StatusBar).set_state(
                "Streaming…", agent.name, agent.model,
                bool(agent.subagents), streaming_mode=True,
            )
            self.run_worker(self._agent_stream(query), exclusive=True, exit_on_error=False)
        else:
            self.query_one(StatusBar).set_state(
                "Thinking…", agent.name, agent.model,
                bool(agent.subagents), streaming_mode=False,
            )
            self.run_worker(self._agent_run(query), exclusive=True, exit_on_error=False)

    async def _agent_run(self, query: str) -> None:
        if self._agent is None:
            return
        try:
            result = await self._agent.run(query)
            self.post_message(AgentResponseReady(result))
        except Exception as exc:
            logger.exception("Agent run failed")
            self.post_message(AgentError(str(exc)))

    async def _agent_stream(self, query: str) -> None:
        if self._agent is None:
            return
        try:
            full_text = ""
            async for chunk in self._agent.stream(query):
                full_text += chunk
            self.post_message(StreamFinished(full_text))
        except Exception as exc:
            logger.exception("Agent stream failed")
            self.post_message(AgentError(str(exc)))

    # ── Message handlers ──────────────────────────────────────────────────────

    def on_tool_call_started(self, event: ToolCallStarted) -> None:
        chat = self.query_one(ChatPanel)
        entry = chat.add_tool_call(event.tool_name, event.arguments)
        self._pending_tools.setdefault(event.tool_name, []).append(entry)

    def on_tool_call_completed(self, event: ToolCallCompleted) -> None:
        queue = self._pending_tools.get(event.tool_name)
        if queue:
            entry = queue.pop(0)
            entry.set_result(event.result)

    def on_turn_started(self, event: TurnStarted) -> None:
        # TurnStarted fires for each LLM call — update status bar only
        if self._agent:
            self.query_one(StatusBar).set_state(
                "Streaming…" if self._streaming_mode else "Thinking…",
                self._agent.name, self._agent.model,
                bool(self._agent.subagents),
                streaming_mode=self._streaming_mode,
            )

    def on_delegation_event_started(self, event: DelegationEventStarted) -> None:
        self.query_one(StatusPanel).set_active_delegation(event.target, event.task)

    def on_stream_chunk_received(self, event: StreamChunkReceived) -> None:
        if self._current_response is None:
            self._current_response = self.query_one(ChatPanel).start_response()
        self._current_response.append_chunk(event.text)

    def on_stream_finished(self, event: StreamFinished) -> None:
        if self._current_response is None:
            # No streaming chunks came through (e.g. empty response)
            entry = self.query_one(ChatPanel).start_response()
            entry.set_text(event.full_text)
        self._current_response = None
        self._finish_turn()

    def on_agent_response_ready(self, event: AgentResponseReady) -> None:
        entry = self.query_one(ChatPanel).start_response()
        entry.set_text(event.text)
        self._finish_turn()

    def on_agent_error(self, event: AgentError) -> None:
        # Render error as an AssistantEntry so it's in-flow
        entry = self.query_one(ChatPanel).start_response()
        entry.set_text(f"[Error] {event.error}")
        self._current_response = None
        if self._agent:
            self.query_one(StatusBar).set_state(
                "Error", self._agent.name, self._agent.model,
                bool(self._agent.subagents), streaming_mode=self._streaming_mode,
            )
        self._re_enable_input()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_toggle_logs(self) -> None:
        self.query_one(LogPanel).toggle_visibility()

    def action_clear_chat(self) -> None:
        self.query_one(ChatPanel).clear_entries()

    def action_orchestrate(self) -> None:
        if self._agent and self._agent.subagents:
            self.push_screen(OrchestrationScreen(self._agent))

    def action_toggle_stream(self) -> None:
        self._streaming_mode = not self._streaming_mode
        mode_label = "streaming" if self._streaming_mode else "batch"
        chat = self.query_one(ChatPanel)
        # Add a brief status note as a user-visible entry
        chat.append_user_message(f"[dim]⚙ Switched to {mode_label} mode[/dim]")
        if self._agent:
            self.query_one(StatusBar).set_state(
                "Ready", self._agent.name, self._agent.model,
                bool(self._agent.subagents), streaming_mode=self._streaming_mode,
            )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _finish_turn(self) -> None:
        """Update stats panels and re-enable input after a completed turn."""
        self.query_one(StatusPanel).clear_active_delegation()
        if self._agent:
            stats = self._agent.get_usage_stats()
            self.query_one(StatusPanel).update_stats(stats)
            self.query_one(StatusBar).set_state(
                "Ready", self._agent.name, self._agent.model,
                bool(self._agent.subagents), streaming_mode=self._streaming_mode,
            )
            token_usage = stats.get("token_usage") or 0
            limit = stats.get("context_window_limit")
            self.query_one(StatusBar).update_token_usage(
                int(token_usage), int(limit) if limit else None
            )
            cost = stats.get("cumulative_cost") or 0.0
            self.query_one(StatusBar).update_session_cost(float(cost))
            if stats.get("compacted_this_turn"):
                self.query_one(ChatPanel).append_user_message(
                    "[dim]⚡ Context compacted[/dim]"
                )
        self._re_enable_input()

    def _re_enable_input(self) -> None:
        inp = self.query_one("#chat-input", HistoryInput)
        inp.disabled = False
        inp.focus()
```

Also remove the now-unused `_stream_buffer` field and the old `on_stream_chunk_received` RichLog-based handler that was replaced. Remove the `OrchestrationScreen` references to `RichLog` for its results — keep the screen as-is (it has its own internal RichLog-free `VerticalScroll` of `Static` widgets already).

**Step 4: Run full test suite**

```bash
pytest tests/test_cli/test_tui.py -v
```

Expected: all pass.

```bash
pytest tests/ -x -q 2>&1 | tail -20
```

Expected: no regressions.

**Step 5: Commit**

```bash
git add sage/cli/tui.py tests/test_cli/test_tui.py
git commit -m "feat(tui): wire SageTUIApp with new layout, status panel, and log toggle"
```

---

## Final Verification

```bash
# Full test run
pytest tests/ -q

# Type check
mypy sage/cli/tui.py --ignore-missing-imports

# Lint
ruff check sage/cli/tui.py
ruff format --check sage/cli/tui.py
```

Manually smoke-test:
```bash
sage tui --agent-config path/to/AGENTS.md
```
- Verify ctrl+q exits cleanly (no hang)
- Verify ctrl+l toggles log panel
- Verify ctrl+shift+l clears chat
- Verify up/down arrow navigates message history
- Verify tool calls appear as collapsible entries
- Verify agent response is mouse-selectable in chat
- Verify status panel updates after a turn

# tests/test_cli/test_tui.py
"""Tests for TUI widgets."""

from __future__ import annotations

from unittest.mock import MagicMock

from textual.app import App, ComposeResult
from textual.widgets import Collapsible, TextArea

from sage.cli.tui import (
    AssistantEntry,
    ChatPanel,
    HistoryInput,
    StatusPanel,
    ThinkingEntry,
    ToolEntry,
    UserEntry,
)


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
        # Type each character of "draft text" individually
        for ch in "draft text":
            await pilot.press(ch)
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
        await pilot.press("up")  # should not crash, stays at "only"
        assert inp.value == "only"


async def test_history_down_at_bottom_is_noop() -> None:
    app = _HistoryApp()
    async with app.run_test() as pilot:
        inp = app.query_one(HistoryInput)
        await pilot.press("down")  # empty history, no crash
        assert inp.value == ""


async def test_history_up_on_empty_history_is_noop() -> None:
    app = _HistoryApp()
    async with app.run_test() as pilot:
        inp = app.query_one(HistoryInput)
        await pilot.press("up")  # empty history, no crash
        assert inp.value == ""


async def test_user_entry_renders_message() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield UserEntry("hello world")

    app = _App()
    async with app.run_test():
        widget = app.query_one(UserEntry)
        assert widget is not None


async def test_thinking_entry_is_mounted() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield ThinkingEntry()

    app = _App()
    async with app.run_test():
        widget = app.query_one(ThinkingEntry)
        assert widget is not None


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


async def test_assistant_entry_text_area_is_read_only() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield AssistantEntry()

    app = _App()
    async with app.run_test():
        ta = app.query_one(TextArea)
        assert ta.read_only is True


async def test_assistant_entry_append_chunk() -> None:
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


async def test_assistant_entry_set_text() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield AssistantEntry()

    app = _App()
    async with app.run_test():
        entry = app.query_one(AssistantEntry)
        entry.set_text("full response here")
        ta = app.query_one(TextArea)
        assert "full response here" in ta.text


async def test_chat_panel_append_user_message() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield ChatPanel(id="chat")

    app = _App()
    async with app.run_test() as pilot:
        panel = app.query_one(ChatPanel)
        panel.append_user_message("test message")
        await pilot.pause()
        assert len(app.query(UserEntry)) == 1


async def test_chat_panel_start_and_finish_turn() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield ChatPanel(id="chat")

    app = _App()
    async with app.run_test() as pilot:
        panel = app.query_one(ChatPanel)
        panel.start_turn()
        await pilot.pause()
        assert len(app.query(ThinkingEntry)) == 1
        panel.start_response()
        await pilot.pause()
        assert len(app.query(ThinkingEntry)) == 0
        assert len(app.query(AssistantEntry)) == 1


async def test_chat_panel_add_tool_call() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield ChatPanel(id="chat")

    app = _App()
    async with app.run_test() as pilot:
        panel = app.query_one(ChatPanel)
        tool = panel.add_tool_call("bash", {"command": "ls"})
        await pilot.pause()
        assert isinstance(tool, ToolEntry)
        assert len(app.query(ToolEntry)) == 1


async def test_chat_panel_clear() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield ChatPanel(id="chat")

    app = _App()
    async with app.run_test() as pilot:
        panel = app.query_one(ChatPanel)
        panel.append_user_message("hi")
        await pilot.pause()
        panel.clear_entries()
        await pilot.pause()
        assert len(app.query(UserEntry)) == 0


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


async def test_status_panel_initializes_without_crash() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield StatusPanel(id="status")

    app = _App()
    async with app.run_test():
        panel = app.query_one(StatusPanel)
        panel.initialize(_make_mock_agent())


async def test_status_panel_update_stats_without_crash() -> None:
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
        panel.update_stats(stats)


async def test_status_panel_active_agents_delegation() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield StatusPanel(id="status")

    app = _App()
    async with app.run_test():
        panel = app.query_one(StatusPanel)
        panel.initialize(_make_mock_agent())
        panel.set_active_delegation("coder", "write a function")
        panel.clear_active_delegation()

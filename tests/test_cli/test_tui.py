# tests/test_cli/test_tui.py
"""Tests for TUI widgets."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from textual.app import App, ComposeResult
from textual.widgets import Collapsible, Markdown

from sage.cli.tui import (
    AssistantEntry,
    ChatPanel,
    HistoryInput,
    LogPanel,
    StatusPanel,
    ThinkingEntry,
    ToolEntry,
    TUILogHandler,
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


async def test_assistant_entry_has_markdown_widget() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield AssistantEntry()

    app = _App()
    async with app.run_test():
        md = app.query_one(Markdown)
        assert md is not None


async def test_assistant_entry_append_chunk() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield AssistantEntry()

    app = _App()
    async with app.run_test() as pilot:
        entry = app.query_one(AssistantEntry)
        entry.append_chunk("hello ")
        entry.append_chunk("world")
        await pilot.pause()
        assert "hello world" in entry._content


async def test_assistant_entry_set_text() -> None:
    class _App(App[None]):
        def compose(self) -> ComposeResult:
            yield AssistantEntry()

    app = _App()
    async with app.run_test() as pilot:
        entry = app.query_one(AssistantEntry)
        entry.set_text("full response here")
        await pilot.pause()
        assert "full response here" in entry._content


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


def test_tui_log_handler_emit_calls_post_message() -> None:
    mock_app = MagicMock()
    handler = TUILogHandler(mock_app)
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello",
        args=(),
        exc_info=None,
    )
    handler.emit(record)
    mock_app.post_message.assert_called_once()


# ── Integration test ──────────────────────────────────────────────────────────


def _make_config_path(tmp_path: Path) -> Path:
    cfg = tmp_path / "AGENTS.md"
    cfg.write_text("---\nname: test-agent\nmodel: gpt-4o\n---\nA helpful assistant.\n")
    return cfg


async def test_sage_tui_app_mounts_and_quits(tmp_path: Path) -> None:
    from sage.cli.tui import SageTUIApp

    cfg = _make_config_path(tmp_path)
    mock_agent = _make_mock_agent()
    mock_agent.close = AsyncMock()

    with patch("sage.cli.tui.Agent.from_config", return_value=mock_agent):
        app = SageTUIApp(config_path=cfg)
        async with app.run_test() as pilot:
            assert app.query_one(ChatPanel) is not None
            assert app.query_one(StatusPanel) is not None
            assert app.query_one(LogPanel) is not None
            await pilot.press("ctrl+q")
        mock_agent.close.assert_awaited_once()

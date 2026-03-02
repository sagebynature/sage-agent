# tests/test_cli/test_tui.py
"""Tests for TUI widgets."""

from __future__ import annotations

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

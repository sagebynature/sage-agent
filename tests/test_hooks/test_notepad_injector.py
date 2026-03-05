from __future__ import annotations

from pathlib import Path

import pytest

from sage.hooks.base import HookEvent
from sage.hooks.builtin.notepad_injector import make_notepad_hook
from sage.models import Message


def _user_msg(content: str) -> Message:
    return Message(role="user", content=content)


def _system_msg(content: str) -> Message:
    return Message(role="system", content=content)


class TestMakeNotepadHookFactory:
    def test_returns_callable(self, tmp_path: Path) -> None:
        hook = make_notepad_hook("plan-a", base_dir=tmp_path)
        assert callable(hook)


class TestHookReturnsNone:
    @pytest.mark.asyncio
    async def test_returns_none_for_non_pre_llm_call_event(self, tmp_path: Path) -> None:
        hook = make_notepad_hook("plan-a", base_dir=tmp_path)
        data = {"messages": [_user_msg("hello")]}
        result = await hook(HookEvent.POST_LLM_CALL, data)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_notepad_is_empty(self, tmp_path: Path) -> None:
        hook = make_notepad_hook("plan-a", base_dir=tmp_path)
        data = {"messages": [_user_msg("hello")]}
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_post_tool_execute_event(self, tmp_path: Path) -> None:
        hook = make_notepad_hook("plan-a", base_dir=tmp_path)
        data = {"messages": [_user_msg("hello")]}
        result = await hook(HookEvent.POST_TOOL_EXECUTE, data)
        assert result is None


class TestHookInjectsNotepad:
    @pytest.mark.asyncio
    async def test_injects_notepad_content_as_system_message(self, tmp_path: Path) -> None:
        from sage.planning.notepad import Notepad

        await Notepad("plan-b", base_dir=tmp_path).write("learnings", "Python is great")
        hook = make_notepad_hook("plan-b", base_dir=tmp_path)
        data = {"messages": [_user_msg("continue")]}
        result = await hook(HookEvent.PRE_LLM_CALL, data)

        assert result is not None
        system_msgs = [m for m in result["messages"] if m.role == "system"]
        assert len(system_msgs) == 1
        assert "[Notepad]" in (system_msgs[0].content or "")
        assert "Python is great" in (system_msgs[0].content or "")

    @pytest.mark.asyncio
    async def test_injects_after_existing_system_message(self, tmp_path: Path) -> None:
        from sage.planning.notepad import Notepad

        await Notepad("plan-c", base_dir=tmp_path).write("notes", "important note")
        hook = make_notepad_hook("plan-c", base_dir=tmp_path)
        data = {"messages": [_system_msg("You are helpful."), _user_msg("go")]}
        result = await hook(HookEvent.PRE_LLM_CALL, data)

        assert result is not None
        messages = result["messages"]
        assert messages[0].content == "You are helpful."
        assert messages[1].role == "system"
        assert "[Notepad]" in (messages[1].content or "")
        assert messages[2].role == "user"

    @pytest.mark.asyncio
    async def test_prepends_when_no_system_message(self, tmp_path: Path) -> None:
        from sage.planning.notepad import Notepad

        await Notepad("plan-d", base_dir=tmp_path).write("notes", "note A")
        hook = make_notepad_hook("plan-d", base_dir=tmp_path)
        data = {"messages": [_user_msg("question")]}
        result = await hook(HookEvent.PRE_LLM_CALL, data)

        assert result is not None
        messages = result["messages"]
        assert messages[0].role == "system"
        assert "[Notepad]" in (messages[0].content or "")
        assert messages[1].role == "user"

    @pytest.mark.asyncio
    async def test_includes_all_sections(self, tmp_path: Path) -> None:
        from sage.planning.notepad import Notepad

        notepad = Notepad("plan-e", base_dir=tmp_path)
        await notepad.write("learnings", "learned X")
        await notepad.write("decisions", "decided Y")
        hook = make_notepad_hook("plan-e", base_dir=tmp_path)
        data = {"messages": [_user_msg("next step")]}
        result = await hook(HookEvent.PRE_LLM_CALL, data)

        assert result is not None
        injected = next(m for m in result["messages"] if m.role == "system")
        content = injected.content or ""
        assert "learned X" in content
        assert "decided Y" in content

    @pytest.mark.asyncio
    async def test_does_not_mutate_original_messages(self, tmp_path: Path) -> None:
        from sage.planning.notepad import Notepad

        await Notepad("plan-f", base_dir=tmp_path).write("notes", "something")
        hook = make_notepad_hook("plan-f", base_dir=tmp_path)
        original = [_user_msg("hi")]
        data = {"messages": original}
        await hook(HookEvent.PRE_LLM_CALL, data)
        assert len(original) == 1

    @pytest.mark.asyncio
    async def test_preserves_extra_data_keys(self, tmp_path: Path) -> None:
        from sage.planning.notepad import Notepad

        await Notepad("plan-g", base_dir=tmp_path).write("notes", "x")
        hook = make_notepad_hook("plan-g", base_dir=tmp_path)
        data = {"messages": [_user_msg("go")], "model": "gpt-4o"}
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result is not None
        assert result["model"] == "gpt-4o"

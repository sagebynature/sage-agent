"""Tests for the auto_memory hook factory."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sage.hooks.base import HookEvent
from sage.hooks.builtin.auto_memory import make_auto_memory_hook
from sage.memory.base import MemoryEntry
from sage.models import Message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_memory(count: int = 3, entries: list[MemoryEntry] | None = None) -> MagicMock:
    """Return a mock memory object with ``count`` and ``recall`` methods."""
    if entries is None:
        entries = [
            MemoryEntry(id="abc", content="python is cool", score=0.9),
            MemoryEntry(id="def", content="async is fast", score=0.8),
        ]

    memory = MagicMock()
    memory.count = AsyncMock(return_value=count)
    memory.recall = AsyncMock(return_value=entries)
    return memory


def _user_msg(content: str) -> Message:
    return Message(role="user", content=content)


def _system_msg(content: str) -> Message:
    return Message(role="system", content=content)


def _assistant_msg(content: str) -> Message:
    return Message(role="assistant", content=content)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMakeAutoMemoryHookFactory:
    def test_returns_callable(self) -> None:
        """make_auto_memory_hook should return a callable."""
        memory = _make_memory()
        hook = make_auto_memory_hook(memory)
        assert callable(hook)

    def test_returns_callable_with_custom_params(self) -> None:
        """Factory with custom max_memories and min_relevance also returns callable."""
        memory = _make_memory()
        hook = make_auto_memory_hook(memory, max_memories=3, min_relevance=0.5)
        assert callable(hook)


class TestHookInjectsMemories:
    @pytest.mark.asyncio
    async def test_injects_memories_when_user_message_exists(self) -> None:
        """Hook should inject memories as a system message when user message is found."""
        entries = [
            MemoryEntry(id="abc", content="python is cool", score=0.9),
            MemoryEntry(id="def", content="async is fast", score=0.8),
        ]
        memory = _make_memory(count=2, entries=entries)
        hook = make_auto_memory_hook(memory)

        data = {"messages": [_user_msg("Tell me about Python")]}
        result = await hook(HookEvent.PRE_LLM_CALL, data)

        assert result is not None
        messages = result["messages"]
        # A system message with memories should be injected
        system_messages = [m for m in messages if m.role == "system"]
        assert len(system_messages) == 1
        content = system_messages[0].content or ""
        assert "[Relevant memories]" in content
        assert "python is cool" in content
        assert "id: abc" in content
        assert "async is fast" in content
        assert "id: def" in content

    @pytest.mark.asyncio
    async def test_memory_injected_prepended_when_no_system_message(self) -> None:
        """Hook should prepend memory message if no system message exists."""
        entries = [MemoryEntry(id="x1", content="fact one", score=1.0)]
        memory = _make_memory(count=1, entries=entries)
        hook = make_auto_memory_hook(memory)

        data = {"messages": [_user_msg("hello")]}
        result = await hook(HookEvent.PRE_LLM_CALL, data)

        assert result is not None
        messages = result["messages"]
        assert messages[0].role == "system"
        assert "fact one" in (messages[0].content or "")

    @pytest.mark.asyncio
    async def test_memory_message_format(self) -> None:
        """Memory message should follow the expected format with numbered entries."""
        entries = [
            MemoryEntry(id="m1", content="first memory", score=0.9),
            MemoryEntry(id="m2", content="second memory", score=0.7),
        ]
        memory = _make_memory(count=2, entries=entries)
        hook = make_auto_memory_hook(memory)

        data = {"messages": [_user_msg("query")]}
        result = await hook(HookEvent.PRE_LLM_CALL, data)

        assert result is not None
        system_content = result["messages"][0].content or ""
        assert "Memory 1: first memory (id: m1)" in system_content
        assert "Memory 2: second memory (id: m2)" in system_content

    @pytest.mark.asyncio
    async def test_returns_updated_data_dict(self) -> None:
        """Hook should return the same data dict with updated messages."""
        entries = [MemoryEntry(id="z1", content="some memory", score=0.5)]
        memory = _make_memory(count=1, entries=entries)
        hook = make_auto_memory_hook(memory)

        data = {"messages": [_user_msg("question")], "extra_key": "extra_value"}
        result = await hook(HookEvent.PRE_LLM_CALL, data)

        assert result is not None
        assert result["extra_key"] == "extra_value"


class TestHookReturnsNone:
    @pytest.mark.asyncio
    async def test_returns_none_for_non_pre_llm_call_event(self) -> None:
        """Hook should return None for non-PRE_LLM_CALL events."""
        memory = _make_memory()
        hook = make_auto_memory_hook(memory)

        data = {"messages": [_user_msg("hello")]}
        result = await hook(HookEvent.POST_LLM_CALL, data)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_pre_tool_call_event(self) -> None:
        """Hook should return None for PRE_TOOL_CALL events."""
        memory = _make_memory()
        hook = make_auto_memory_hook(memory)

        data = {"messages": [_user_msg("hello")]}
        result = await hook(HookEvent.PRE_TOOL_EXECUTE, data)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_memory_is_empty(self) -> None:
        """Hook should return None when memory count is 0."""
        memory = _make_memory(count=0, entries=[])
        hook = make_auto_memory_hook(memory)

        data = {"messages": [_user_msg("hello")]}
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result is None
        memory.recall.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_user_message(self) -> None:
        """Hook should return None when there is no user message in messages."""
        memory = _make_memory(count=2)
        hook = make_auto_memory_hook(memory)

        data = {"messages": [_system_msg("You are a helpful assistant.")]}
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_messages_empty(self) -> None:
        """Hook should return None when messages list is empty."""
        memory = _make_memory(count=2)
        hook = make_auto_memory_hook(memory)

        data = {"messages": []}
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_recall_returns_empty(self) -> None:
        """Hook should return None when recall returns no entries."""
        memory = _make_memory(count=3, entries=[])
        hook = make_auto_memory_hook(memory)

        data = {"messages": [_user_msg("hello")]}
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result is None


class TestHookRespectMaxMemories:
    @pytest.mark.asyncio
    async def test_respects_max_memories_limit(self) -> None:
        """Hook should pass max_memories as limit to recall."""
        entries = [MemoryEntry(id=f"id{i}", content=f"memory {i}", score=0.9) for i in range(10)]
        memory = _make_memory(count=10, entries=entries[:3])
        hook = make_auto_memory_hook(memory, max_memories=3)

        data = {"messages": [_user_msg("test query")]}
        await hook(HookEvent.PRE_LLM_CALL, data)

        memory.recall.assert_called_once_with(query="test query", limit=3)

    @pytest.mark.asyncio
    async def test_default_max_memories_is_5(self) -> None:
        """Default max_memories should be 5."""
        memory = _make_memory(count=10, entries=[])
        hook = make_auto_memory_hook(memory)

        data = {"messages": [_user_msg("test")]}
        await hook(HookEvent.PRE_LLM_CALL, data)

        memory.recall.assert_called_once_with(query="test", limit=5)


class TestHookSystemMessagePositioning:
    @pytest.mark.asyncio
    async def test_memory_injected_after_first_system_message(self) -> None:
        """Memory message should be inserted AFTER the first system message."""
        entries = [MemoryEntry(id="m1", content="relevant fact", score=0.9)]
        memory = _make_memory(count=1, entries=entries)
        hook = make_auto_memory_hook(memory)

        system_msg = _system_msg("You are a helpful assistant.")
        user_msg = _user_msg("What is Python?")
        data = {"messages": [system_msg, user_msg]}
        result = await hook(HookEvent.PRE_LLM_CALL, data)

        assert result is not None
        messages = result["messages"]
        # Original system message should remain first
        assert messages[0].content == "You are a helpful assistant."
        # Memory system message should be second
        assert messages[1].role == "system"
        assert "[Relevant memories]" in (messages[1].content or "")
        # User message should be last
        assert messages[2].role == "user"

    @pytest.mark.asyncio
    async def test_memory_injected_after_first_system_only(self) -> None:
        """When multiple system messages exist, inject after the FIRST one only."""
        entries = [MemoryEntry(id="m1", content="memory fact", score=0.9)]
        memory = _make_memory(count=1, entries=entries)
        hook = make_auto_memory_hook(memory)

        data = {
            "messages": [
                _system_msg("First system message"),
                _system_msg("Second system message"),
                _user_msg("User query"),
            ]
        }
        result = await hook(HookEvent.PRE_LLM_CALL, data)

        assert result is not None
        messages = result["messages"]
        assert messages[0].content == "First system message"
        assert messages[1].role == "system"
        assert "[Relevant memories]" in (messages[1].content or "")
        assert messages[2].content == "Second system message"
        assert messages[3].role == "user"

    @pytest.mark.asyncio
    async def test_original_messages_not_mutated(self) -> None:
        """Hook should not mutate the original messages list."""
        entries = [MemoryEntry(id="m1", content="some memory", score=0.9)]
        memory = _make_memory(count=1, entries=entries)
        hook = make_auto_memory_hook(memory)

        original_messages = [_user_msg("hello")]
        data = {"messages": original_messages}
        result = await hook(HookEvent.PRE_LLM_CALL, data)

        assert result is not None
        # Original list should still have only one message
        assert len(original_messages) == 1


class TestHookLatestUserMessage:
    @pytest.mark.asyncio
    async def test_uses_latest_user_message_as_query(self) -> None:
        """Hook should use the LAST user message (not the first) as the recall query."""
        entries = [MemoryEntry(id="m1", content="result", score=0.9)]
        memory = _make_memory(count=2, entries=entries)
        hook = make_auto_memory_hook(memory)

        data = {
            "messages": [
                _user_msg("first user message"),
                _assistant_msg("assistant response"),
                _user_msg("latest user message"),
            ]
        }
        await hook(HookEvent.PRE_LLM_CALL, data)

        memory.recall.assert_called_once_with(query="latest user message", limit=5)

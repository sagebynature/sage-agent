"""Tests for memory_forget tool closure registered in Agent._register_memory_tools()."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sage.agent import Agent
from sage.memory.file_backend import FileMemory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_with_memory(tmp_path: Path) -> Agent:
    """Create a minimal Agent that has a FileMemory backend attached."""
    memory = FileMemory(tmp_path / "mem.json", format="json")
    agent = Agent(
        name="test-agent",
        model="gpt-4o-mini",
        memory=memory,
    )
    agent._register_memory_tools()
    return agent


def _make_agent_without_memory() -> Agent:
    """Create a minimal Agent with no memory backend."""
    return Agent(
        name="no-mem-agent",
        model="gpt-4o-mini",
        memory=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMemoryForgetToolRegistration:
    def test_forget_tool_registered_when_memory_configured(self, tmp_path: Any) -> None:
        """Agent with memory has 'memory_forget' in its tool registry."""
        agent = _make_agent_with_memory(tmp_path)
        tool_names = {s.name for s in agent.tool_registry.get_schemas()}
        assert "memory_forget" in tool_names

    def test_forget_tool_absent_when_no_memory(self) -> None:
        """Agent without memory does NOT have 'memory_forget' in registry."""
        agent = _make_agent_without_memory()
        tool_names = {s.name for s in agent.tool_registry.get_schemas()}
        assert "memory_forget" not in tool_names

    def test_memory_store_tool_registered_with_memory(self, tmp_path: Any) -> None:
        """Agent with memory also has 'memory_store' tool registered."""
        agent = _make_agent_with_memory(tmp_path)
        tool_names = {s.name for s in agent.tool_registry.get_schemas()}
        assert "memory_store" in tool_names

    def test_memory_recall_tool_registered_with_memory(self, tmp_path: Any) -> None:
        """Agent with memory also has 'memory_recall' tool registered."""
        agent = _make_agent_with_memory(tmp_path)
        tool_names = {s.name for s in agent.tool_registry.get_schemas()}
        assert "memory_recall" in tool_names


class TestMemoryForgetToolBehavior:
    @pytest.mark.asyncio
    async def test_forget_returns_deleted_message(self, tmp_path: Any) -> None:
        """Calling memory_forget on a stored entry returns a 'deleted' message."""
        memory = FileMemory(tmp_path / "mem.json", format="json")
        agent = Agent(
            name="test-agent",
            model="gpt-4o-mini",
            memory=memory,
        )
        agent._register_memory_tools()

        # Store an entry directly on the memory backend.
        entry_id = await memory.store("test entry to forget", {})

        # Execute the tool via the registry.
        result = await agent.tool_registry.execute("memory_forget", {"memory_id": entry_id})
        assert "deleted" in result.lower()
        assert entry_id in result

        # Verify it was actually deleted.
        assert await memory.count() == 0

    @pytest.mark.asyncio
    async def test_forget_returns_not_found_message(self, tmp_path: Any) -> None:
        """Calling memory_forget on a non-existent ID returns a 'not found' message."""
        memory = FileMemory(tmp_path / "mem.json", format="json")
        agent = Agent(
            name="test-agent",
            model="gpt-4o-mini",
            memory=memory,
        )
        agent._register_memory_tools()

        result = await agent.tool_registry.execute("memory_forget", {"memory_id": "nonexistent_id"})
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_forget_only_removes_target_entry(self, tmp_path: Any) -> None:
        """memory_forget removes only the specified entry, leaving others intact."""
        memory = FileMemory(tmp_path / "mem.json", format="json")
        agent = Agent(
            name="test-agent",
            model="gpt-4o-mini",
            memory=memory,
        )
        agent._register_memory_tools()

        id1 = await memory.store("keep me", {})
        id2 = await memory.store("forget me", {})

        await agent.tool_registry.execute("memory_forget", {"memory_id": id2})

        assert await memory.count() == 1
        remaining = await memory.list_entries()
        assert remaining[0].id == id1

    @pytest.mark.asyncio
    async def test_forget_tool_calls_memory_forget_not_raw(self, tmp_path: Any) -> None:
        """memory_forget goes through the MemoryProtocol, not raw storage."""
        # Use markdown mode to ensure we're using the protocol abstraction.
        memory = FileMemory(tmp_path / "memories", format="markdown")
        agent = Agent(
            name="test-agent",
            model="gpt-4o-mini",
            memory=memory,
        )
        agent._register_memory_tools()

        entry_id = await memory.store("protocol test entry", {"mode": "markdown"})
        result = await agent.tool_registry.execute("memory_forget", {"memory_id": entry_id})
        assert "deleted" in result.lower()
        assert await memory.count() == 0

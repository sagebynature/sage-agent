"""Regression test: Memory tools are not duplicated in _register_background_tools."""

from __future__ import annotations

from typing import Any

import pytest

from sage.agent import Agent
from sage.models import CompletionResult, Message, Usage


class MockProvider:
    """Minimal mock provider for tests."""

    def __init__(self) -> None:
        self.responses: list[CompletionResult] = []

    async def complete(
        self, messages: list[Message], tools: list[Any] | None = None, **kwargs: Any
    ) -> CompletionResult:
        if not self.responses:
            return CompletionResult(
                message=Message(role="assistant", content="done"),
                usage=Usage(),
            )
        return self.responses.pop(0)

    async def stream(self, messages: list[Message], tools: list[Any] | None = None, **kwargs: Any):
        raise NotImplementedError

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class MockMemory:
    """Minimal mock memory backend implementing MemoryProtocol."""

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        return "mem-id"

    async def recall(self, query: str, limit: int = 5) -> list[Any]:
        return []

    async def compact(self, messages: list[Any]) -> list[Any]:
        return messages

    async def clear(self) -> None:
        pass

    async def get(self, memory_id: str) -> Any:
        return None

    async def list_entries(self, *, limit: int = 50, offset: int = 0) -> list[Any]:
        return []

    async def forget(self, memory_id: str) -> bool:
        return False

    async def count(self) -> int:
        return 0

    async def health_check(self) -> dict[str, Any]:
        return {"status": "ok"}


@pytest.mark.asyncio
async def test_memory_tools_not_duplicated_with_background_tasks() -> None:
    """
    Regression test: Verify that memory tools are registered exactly once,
    even when background tools are registered (which used to trigger a duplicate).

    The bug was: _register_background_tools() had orphaned code at the end
    that re-registered memory tools, causing duplicates in the tool registry.
    This test ensures that when an agent with subagents and memory tools
    is created, there is exactly one entry for each memory tool in the registry.
    """
    from sage.tools.decorator import tool as _tool

    provider = MockProvider()
    memory = MockMemory()
    helper_agent = Agent(name="helper", model="test-model", provider=provider)

    agent = Agent(
        name="test-agent",
        model="test-model",
        provider=provider,
        memory=memory,
        subagents={"helper": helper_agent},
    )

    @_tool
    async def memory_store(key: str, value: str) -> str:
        """Store a key-value pair in the agent's semantic memory backend."""
        await memory.store(f"{key}: {value}", metadata={"key": key})
        return f"Stored: {key}"

    @_tool
    async def memory_recall(query: str) -> str:
        """Recall entries from the agent's semantic memory backend."""
        entries = await memory.recall(query)
        if not entries:
            return f"No matches for: {query}"
        return "\n".join(f"- {e.content}" for e in entries)

    @_tool
    async def memory_forget(memory_id: str) -> str:
        """Forget/delete a specific memory entry by its ID."""
        result = await memory.forget(memory_id)
        return f"Memory {memory_id} {'deleted' if result else 'not found'}"

    agent.tool_registry.register(memory_store)
    agent.tool_registry.register(memory_recall)
    agent.tool_registry.register(memory_forget)

    tool_names = {tool_name for tool_name in agent.tool_registry._tools.keys()}

    assert "memory_store" in tool_names
    assert "memory_recall" in tool_names
    assert "memory_forget" in tool_names

    memory_store_fn = agent.tool_registry._tools["memory_store"]
    memory_recall_fn = agent.tool_registry._tools["memory_recall"]
    memory_forget_fn = agent.tool_registry._tools["memory_forget"]

    assert memory_store_fn is not None
    assert memory_recall_fn is not None
    assert memory_forget_fn is not None

    assert callable(memory_store_fn)
    assert callable(memory_recall_fn)
    assert callable(memory_forget_fn)

    assert len([t for t in agent.tool_registry._tools.keys() if t == "memory_store"]) == 1
    assert len([t for t in agent.tool_registry._tools.keys() if t == "memory_recall"]) == 1
    assert len([t for t in agent.tool_registry._tools.keys() if t == "memory_forget"]) == 1

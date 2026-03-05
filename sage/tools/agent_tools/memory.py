from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sage.agent import Agent


def register_memory_tools(agent: "Agent") -> None:
    if agent.memory is None:
        return

    from sage.tools.decorator import tool as _tool

    memory_ref = agent.memory

    @_tool
    async def memory_store(key: str, value: str) -> str:
        """Store a key-value pair in the agent's semantic memory backend."""
        await memory_ref.store(f"{key}: {value}", metadata={"key": key})
        return f"Stored: {key}"

    @_tool
    async def memory_recall(query: str) -> str:
        """Recall entries from the agent's semantic memory backend."""
        entries = await memory_ref.recall(query)
        if not entries:
            return f"No matches for: {query}"
        return "\n".join(f"- {e.content}" for e in entries)

    @_tool
    async def memory_forget(memory_id: str) -> str:
        """Forget/delete a specific memory entry by its ID."""
        result = await memory_ref.forget(memory_id)
        return f"Memory {memory_id} {'deleted' if result else 'not found'}"

    agent.tool_registry.register(memory_store)
    agent.tool_registry.register(memory_recall)
    agent.tool_registry.register(memory_forget)

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sage.models import ToolMetadata, ToolResourceRef, ToolResult

if TYPE_CHECKING:
    from sage.agent import Agent
    from sage.memory.base import MemoryEntry


def _serialize_entry(entry: "MemoryEntry") -> dict[str, Any]:
    return {
        "id": entry.id,
        "content": entry.content,
        "metadata": dict(entry.metadata),
        "score": entry.score,
        "created_at": entry.created_at,
    }


def register_memory_tools(agent: "Agent") -> None:
    if agent.memory is None:
        return

    from sage.tools.decorator import tool as _tool

    memory_ref = agent.memory
    backend_name = type(memory_ref).__name__.removesuffix("Memory").lower() or "memory"

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

    @_tool
    async def memory_add(
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Store a memory entry and return its assigned memory ID."""
        memory_id = await memory_ref.store(content, metadata or {})
        return ToolResult(
            text=f"Stored memory {memory_id}",
            resource=ToolResourceRef(kind="memory", resource_id=memory_id),
            metadata={"memory_id": memory_id},
        )

    @_tool
    async def memory_search(query: str, limit: int = 5) -> ToolResult:
        """Search semantic memory and return ranked matching entries."""
        entries = await memory_ref.recall(query, limit=limit)
        payload = [_serialize_entry(entry) for entry in entries]
        return ToolResult(
            text=f"Found {len(payload)} memories for {query}",
            data={"query": query, "count": len(payload), "entries": payload},
        )

    @_tool
    async def memory_get(memory_id: str) -> ToolResult:
        """Fetch a single memory entry by ID."""
        entry = await memory_ref.get(memory_id)
        if entry is None:
            return ToolResult(
                text=f"Memory {memory_id} not found",
                data={"found": False, "memory_id": memory_id},
            )
        return ToolResult(
            text=f"Loaded memory {memory_id}",
            data={"found": True, "entry": _serialize_entry(entry)},
            resource=ToolResourceRef(kind="memory", resource_id=memory_id),
        )

    @_tool
    async def memory_list(limit: int = 50, offset: int = 0) -> ToolResult:
        """List stored memory entries with pagination."""
        entries = await memory_ref.list_entries(limit=limit, offset=offset)
        payload = [_serialize_entry(entry) for entry in entries]
        return ToolResult(
            text=f"Listed {len(payload)} memories",
            data={
                "count": len(payload),
                "limit": limit,
                "offset": offset,
                "entries": payload,
            },
        )

    @_tool
    async def memory_delete(memory_id: str) -> ToolResult:
        """Delete a memory entry by ID."""
        deleted = await memory_ref.forget(memory_id)
        return ToolResult(
            text=f"Memory {memory_id} {'deleted' if deleted else 'not found'}",
            data={"memory_id": memory_id, "deleted": deleted},
            resource=ToolResourceRef(kind="memory", resource_id=memory_id),
        )

    @_tool
    async def memory_stats() -> ToolResult:
        """Return memory backend status and entry counts."""
        health = dict(await memory_ref.health_check())
        health.setdefault("backend", backend_name)
        if "count" not in health:
            health["count"] = await memory_ref.count()
        return ToolResult(
            text=f"Memory backend {health.get('backend', backend_name)} has {health['count']} entries",
            data=health,
        )

    for fn in (memory_add, memory_search, memory_get, memory_list, memory_delete, memory_stats):
        fn.__tool_schema__.metadata = ToolMetadata(
            risk_level="low",
            stateful=True,
            resource_kind="memory",
            approval_hint="Reads or updates the agent memory store.",
        )

    agent.tool_registry.register(memory_store)
    agent.tool_registry.register(memory_recall)
    agent.tool_registry.register(memory_forget)
    agent.tool_registry.register(memory_add)
    agent.tool_registry.register(memory_search)
    agent.tool_registry.register(memory_get)
    agent.tool_registry.register(memory_list)
    agent.tool_registry.register(memory_delete)
    agent.tool_registry.register(memory_stats)

"""Auto memory hook — injects relevant memories before each LLM call."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from sage.hooks.base import HookEvent
from sage.models import Message

if TYPE_CHECKING:
    from sage.memory.base import MemoryProtocol


def make_auto_memory_hook(
    memory: MemoryProtocol,
    *,
    max_memories: int = 5,
    min_relevance: float = 0.0,
) -> Callable[..., Any]:
    """Return a ``PRE_LLM_CALL`` async hook that injects relevant memories.

    The hook searches *memory* for entries semantically similar to the latest
    user message and injects them as a system-level context block into the
    message list **before** the LLM call is made.

    Args:
        memory: A :class:`~sage.memory.base.MemoryProtocol` backend.
        max_memories: Maximum number of memory entries to inject (default 5).
        min_relevance: Minimum relevance score for a memory entry to be
            included.  Entries with ``score < min_relevance`` are filtered out.
            Defaults to ``0.0`` (include all returned entries).

    Returns:
        An async hook callable compatible with the ``PRE_LLM_CALL`` event.
    """

    async def _hook(event: HookEvent, data: dict[str, Any]) -> dict[str, Any] | None:
        # Only handle PRE_LLM_CALL events.
        if event is not HookEvent.PRE_LLM_CALL:
            return None

        messages: list[Message] = data.get("messages", [])

        # Find the latest user message (search from end).
        user_message_content: str | None = None
        for msg in reversed(messages):
            if msg.role == "user" and msg.content:
                user_message_content = msg.content
                break

        if user_message_content is None:
            return None

        # Check memory count — skip if memory is empty.
        if hasattr(memory, "count"):
            count = await memory.count()
            if count == 0:
                return None

        # Recall relevant memories.
        entries = await memory.recall(query=user_message_content, limit=max_memories)

        if not entries:
            return None

        # Filter by minimum relevance score.
        if min_relevance > 0.0:
            entries = [e for e in entries if e.score >= min_relevance]
            if not entries:
                return None

        # Build system message content.
        lines = ["[Relevant memories]"]
        for i, entry in enumerate(entries, start=1):
            lines.append(f"- Memory {i}: {entry.content} (id: {entry.id})")
        memory_content = "\n".join(lines)

        memory_message = Message(role="system", content=memory_content)

        # Inject the memory message:
        # - AFTER the first system message if one exists
        # - Prepend if no system message
        updated_messages: list[Message] = list(messages)
        first_system_idx: int | None = None
        for idx, msg in enumerate(updated_messages):
            if msg.role == "system":
                first_system_idx = idx
                break

        if first_system_idx is not None:
            updated_messages.insert(first_system_idx + 1, memory_message)
        else:
            updated_messages.insert(0, memory_message)

        data["messages"] = updated_messages
        return data

    return _hook

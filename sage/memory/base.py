"""Base protocol and models for the memory system."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from sage.models import Message


class MemoryEntry(BaseModel):
    """A single memory entry returned from recall operations."""

    id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0
    created_at: str = ""


@runtime_checkable
class MemoryProtocol(Protocol):
    """Protocol that all memory backends must implement."""

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store content and return the assigned memory ID."""
        ...

    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Recall memories ranked by semantic similarity to *query*."""
        ...

    async def compact(self, messages: list[Message]) -> list[Message]:
        """Compact older messages into summaries."""
        ...

    async def clear(self) -> None:
        """Remove all stored memories."""
        ...

"""Base protocol and models for the memory system."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, Field

from sage.models import Message


class MemoryEntry(BaseModel):
    """A single memory entry returned from recall operations."""

    id: str = Field(default_factory=lambda: uuid4().hex)
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

    async def get(self, memory_id: str) -> "MemoryEntry | None":
        """Retrieve a single memory entry by its ID, or None if not found."""
        ...

    async def list_entries(self, *, limit: int = 50, offset: int = 0) -> "list[MemoryEntry]":
        """List stored entries ordered by recency, with pagination support."""
        ...

    async def forget(self, memory_id: str) -> bool:
        """Delete the entry with *memory_id*. Return True if found and deleted, False if not found."""
        ...

    async def count(self) -> int:
        """Return the total number of stored memory entries."""
        ...

    async def health_check(self) -> "dict[str, Any]":
        """Return a health status dictionary, e.g. {"status": "ok", "backend": "sqlite", "count": 42}."""
        ...

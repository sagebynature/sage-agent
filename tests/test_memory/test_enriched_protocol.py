"""Tests for the enriched MemoryProtocol — get/list_entries/forget/count/health_check."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import pytest

from sage.memory.sqlite_backend import SQLiteMemory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class DeterministicEmbedding:
    """Produces deterministic embeddings based on content hashing.

    Copied from tests.test_memory.test_sqlite to avoid cross-module import
    issues (tests/ lacks an __init__.py at the top level).
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            raw = np.array([b / 255.0 for b in digest[:8]], dtype=np.float64)
            norm = np.linalg.norm(raw)
            vec = (raw / norm if norm > 0 else raw).tolist()
            result.append(vec)
        return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def memory(tmp_path: Any) -> SQLiteMemory:
    db_path = str(tmp_path / "test_enriched.db")
    mem = SQLiteMemory(path=db_path, embedding=DeterministicEmbedding())
    await mem.initialize()
    try:
        yield mem  # type: ignore[misc]
    finally:
        await mem.close()


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


class TestGet:
    @pytest.mark.asyncio
    async def test_get_existing_entry(self, memory: SQLiteMemory) -> None:
        """store, list to get id, get(id) → returns entry."""
        await memory.store("hello world", {"tag": "test"})
        entries = await memory.list_entries()
        assert len(entries) == 1
        eid = entries[0].id
        got = await memory.get(eid)
        assert got is not None
        assert got.content == "hello world"
        assert got.id == eid

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, memory: SQLiteMemory) -> None:
        """get('nonexistent') → None."""
        result = await memory.get("nonexistent_id_that_does_not_exist")
        assert result is None


# ---------------------------------------------------------------------------
# list_entries()
# ---------------------------------------------------------------------------


class TestListEntries:
    @pytest.mark.asyncio
    async def test_list_entries_basic(self, memory: SQLiteMemory) -> None:
        """store 3, list_entries() → 3 entries."""
        await memory.store("entry one")
        await memory.store("entry two")
        await memory.store("entry three")
        entries = await memory.list_entries()
        assert len(entries) == 3

    @pytest.mark.asyncio
    async def test_list_entries_limit(self, memory: SQLiteMemory) -> None:
        """store 5, list_entries(limit=2) → 2 entries."""
        for i in range(5):
            await memory.store(f"item {i}")
        entries = await memory.list_entries(limit=2)
        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_list_entries_offset(self, memory: SQLiteMemory) -> None:
        """store 5, list_entries(limit=2, offset=2) → 2 different entries than first 2."""
        for i in range(5):
            await memory.store(f"item {i}")
        first_two = await memory.list_entries(limit=2, offset=0)
        next_two = await memory.list_entries(limit=2, offset=2)
        assert len(next_two) == 2
        first_ids = {e.id for e in first_two}
        next_ids = {e.id for e in next_two}
        # The two pages should not overlap
        assert first_ids.isdisjoint(next_ids)

    @pytest.mark.asyncio
    async def test_list_entries_empty(self, memory: SQLiteMemory) -> None:
        """list_entries() on empty database → []."""
        entries = await memory.list_entries()
        assert entries == []


# ---------------------------------------------------------------------------
# forget()
# ---------------------------------------------------------------------------


class TestForget:
    @pytest.mark.asyncio
    async def test_forget_existing(self, memory: SQLiteMemory) -> None:
        """store, get id, forget(id) → True, count() → 0."""
        await memory.store("to be forgotten")
        entries = await memory.list_entries()
        eid = entries[0].id
        result = await memory.forget(eid)
        assert result is True
        assert await memory.count() == 0

    @pytest.mark.asyncio
    async def test_forget_nonexistent(self, memory: SQLiteMemory) -> None:
        """forget('nonexistent') → False."""
        result = await memory.forget("this_id_does_not_exist")
        assert result is False

    @pytest.mark.asyncio
    async def test_forget_leaves_others_intact(self, memory: SQLiteMemory) -> None:
        """Forgetting one entry does not affect others."""
        id1 = await memory.store("keep me")
        id2 = await memory.store("delete me")
        await memory.forget(id2)
        assert await memory.count() == 1
        kept = await memory.get(id1)
        assert kept is not None
        assert kept.content == "keep me"


# ---------------------------------------------------------------------------
# count()
# ---------------------------------------------------------------------------


class TestCount:
    @pytest.mark.asyncio
    async def test_count_empty(self, memory: SQLiteMemory) -> None:
        """count() on empty database → 0."""
        assert await memory.count() == 0

    @pytest.mark.asyncio
    async def test_count(self, memory: SQLiteMemory) -> None:
        """store 3, count() → 3."""
        await memory.store("one")
        await memory.store("two")
        await memory.store("three")
        assert await memory.count() == 3

    @pytest.mark.asyncio
    async def test_count_after_clear(self, memory: SQLiteMemory) -> None:
        """count() → 0 after clear()."""
        await memory.store("temp")
        await memory.clear()
        assert await memory.count() == 0


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_status_ok(self, memory: SQLiteMemory) -> None:
        """health_check() → dict with status='ok'."""
        result = await memory.health_check()
        assert isinstance(result, dict)
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_check_has_backend(self, memory: SQLiteMemory) -> None:
        """health_check() → dict with backend='sqlite'."""
        result = await memory.health_check()
        assert result["backend"] == "sqlite"

    @pytest.mark.asyncio
    async def test_health_check_count_matches(self, memory: SQLiteMemory) -> None:
        """health_check() count field matches actual count."""
        await memory.store("test entry")
        result = await memory.health_check()
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_health_check_has_path(self, memory: SQLiteMemory) -> None:
        """health_check() → dict with path field."""
        result = await memory.health_check()
        assert "path" in result


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_memory_entry_has_id_field(self) -> None:
        """MemoryEntry.id should be auto-generated if not provided."""
        from sage.memory.base import MemoryEntry

        entry = MemoryEntry(content="test", metadata={})
        assert isinstance(entry.id, str)
        assert len(entry.id) > 0

    def test_protocol_has_new_methods(self) -> None:
        """MemoryProtocol should expose the new methods."""
        from sage.memory.base import MemoryProtocol

        public_methods = [m for m in dir(MemoryProtocol) if not m.startswith("_")]
        assert "get" in public_methods
        assert "list_entries" in public_methods
        assert "forget" in public_methods
        assert "count" in public_methods
        assert "health_check" in public_methods

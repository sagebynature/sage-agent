"""Tests for SQLiteMemory backend."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import pytest

from sage.exceptions import SageMemoryError
from sage.memory.base import MemoryEntry
from sage.memory.sqlite_backend import SQLiteMemory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class DeterministicEmbedding:
    """Produces deterministic embeddings based on content hashing.

    Each call returns a normalised 8-dimensional vector derived from a
    SHA-256 digest so that different texts yield reproducibly different
    vectors while identical texts yield the same vector.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            # Interpret bytes as uint8 and convert to float64 for safe arithmetic
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
    db_path = str(tmp_path / "test_memory.db")
    mem = SQLiteMemory(path=db_path, embedding=DeterministicEmbedding())
    await mem.initialize()
    yield mem  # type: ignore[misc]
    await mem.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSQLiteMemoryStore:
    @pytest.mark.asyncio
    async def test_store_returns_id(self, memory: SQLiteMemory) -> None:
        mid = await memory.store("hello world")
        assert isinstance(mid, str)
        assert len(mid) == 32  # uuid4 hex

    @pytest.mark.asyncio
    async def test_store_with_metadata(self, memory: SQLiteMemory) -> None:
        meta = {"source": "test", "priority": 1}
        mid = await memory.store("with metadata", metadata=meta)
        results = await memory.recall("with metadata", limit=1)
        assert len(results) == 1
        assert results[0].id == mid
        assert results[0].metadata == meta

    @pytest.mark.asyncio
    async def test_store_creates_timestamp(self, memory: SQLiteMemory) -> None:
        await memory.store("timestamped")
        results = await memory.recall("timestamped", limit=1)
        assert results[0].created_at != ""


class TestSQLiteMemoryRecall:
    @pytest.mark.asyncio
    async def test_recall_returns_memory_entries(self, memory: SQLiteMemory) -> None:
        await memory.store("alpha")
        results = await memory.recall("alpha")
        assert all(isinstance(r, MemoryEntry) for r in results)

    @pytest.mark.asyncio
    async def test_recall_exact_match_highest_score(self, memory: SQLiteMemory) -> None:
        await memory.store("the quick brown fox")
        await memory.store("lazy dog sleeps")
        await memory.store("something completely different")

        results = await memory.recall("the quick brown fox", limit=3)
        assert results[0].content == "the quick brown fox"
        assert results[0].score == pytest.approx(1.0, abs=1e-5)

    @pytest.mark.asyncio
    async def test_recall_respects_limit(self, memory: SQLiteMemory) -> None:
        for i in range(10):
            await memory.store(f"memory entry {i}")
        results = await memory.recall("memory entry 0", limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_recall_sorted_descending(self, memory: SQLiteMemory) -> None:
        await memory.store("apple pie recipe")
        await memory.store("banana bread recipe")
        await memory.store("cherry tart recipe")

        results = await memory.recall("apple pie recipe", limit=3)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_recall_empty_database(self, memory: SQLiteMemory) -> None:
        results = await memory.recall("anything")
        assert results == []


class TestSQLiteMemoryClear:
    @pytest.mark.asyncio
    async def test_clear_removes_all(self, memory: SQLiteMemory) -> None:
        await memory.store("one")
        await memory.store("two")
        await memory.clear()
        results = await memory.recall("one")
        assert results == []


class TestSQLiteMemoryCompact:
    @pytest.mark.asyncio
    async def test_compact_is_passthrough(self, memory: SQLiteMemory) -> None:
        from sage.models import Message

        msgs = [Message(role="user", content="hi")]
        assert await memory.compact(msgs) is msgs


class TestSQLiteMemoryLifecycle:
    @pytest.mark.asyncio
    async def test_operations_before_init_raise(self, tmp_path: Any) -> None:
        mem = SQLiteMemory(
            path=str(tmp_path / "uninit.db"),
            embedding=DeterministicEmbedding(),
        )
        with pytest.raises(SageMemoryError, match="not initialized"):
            await mem.store("fail")

    @pytest.mark.asyncio
    async def test_close_and_reopen(self, tmp_path: Any) -> None:
        db_path = str(tmp_path / "reopen.db")
        emb = DeterministicEmbedding()

        mem = SQLiteMemory(path=db_path, embedding=emb)
        await mem.initialize()
        mid = await mem.store("persistent")
        await mem.close()

        mem2 = SQLiteMemory(path=db_path, embedding=emb)
        await mem2.initialize()
        results = await mem2.recall("persistent", limit=1)
        assert len(results) == 1
        assert results[0].id == mid
        await mem2.close()

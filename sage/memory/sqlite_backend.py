"""SQLite-backed memory with vector similarity search."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite
import numpy as np
import numpy.typing as npt

from sage.exceptions import SageMemoryError
from sage.memory.base import MemoryEntry
from sage.memory.embedding import EmbeddingProtocol
from sage.models import Message

logger = logging.getLogger(__name__)


class SQLiteMemory:
    """SQLite-backed memory with cosine-similarity vector search.

    Call :meth:`initialize` before any other operation to create the
    database schema.
    """

    def __init__(
        self,
        path: str = "memory.db",
        *,
        embedding: EmbeddingProtocol,
    ) -> None:
        self._path = path
        self._embedding = embedding
        self._db: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Open the database and ensure the schema exists."""
        logger.info("Opening memory database at %s", self._path)
        self._db = await aiosqlite.connect(self._path)
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id         TEXT PRIMARY KEY,
                content    TEXT NOT NULL,
                embedding  BLOB,
                metadata   TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """
        )
        await self._db.commit()
        logger.info("Memory database schema ensured")

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            logger.debug("Closing memory database connection")
            await self._db.close()
            self._db = None

    # ------------------------------------------------------------------
    # MemoryProtocol
    # ------------------------------------------------------------------

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store *content* with an embedding and return the memory ID."""
        self._ensure_open()

        memory_id = uuid.uuid4().hex
        vectors = await self._embedding.embed([content])
        embedding_blob = np.array(vectors[0], dtype=np.float32).tobytes()
        meta_json = json.dumps(metadata or {})
        created_at = datetime.now(timezone.utc).isoformat()

        await self._db.execute(  # type: ignore[union-attr]
            "INSERT INTO memories (id, content, embedding, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
            (memory_id, content, embedding_blob, meta_json, created_at),
        )
        await self._db.commit()  # type: ignore[union-attr]
        logger.debug("Stored memory id=%s, content_preview=%.80s", memory_id, content)
        return memory_id

    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Return the top-*limit* memories ranked by cosine similarity."""
        self._ensure_open()
        logger.debug("Recalling memories: query_preview=%.80s, limit=%d", query, limit)

        query_vectors = await self._embedding.embed([query])
        query_vec = np.array(query_vectors[0], dtype=np.float32)

        cursor = await self._db.execute(  # type: ignore[union-attr]
            "SELECT id, content, embedding, metadata, created_at FROM memories"
        )
        rows = await cursor.fetchall()

        scored: list[tuple[float, MemoryEntry]] = []
        for row_id, content, emb_blob, meta_json, created_at in rows:
            stored_vec = np.frombuffer(emb_blob, dtype=np.float32)
            score = self._cosine_similarity(query_vec, stored_vec)
            entry = MemoryEntry(
                id=row_id,
                content=content,
                metadata=json.loads(meta_json),
                score=float(score),
                created_at=created_at,
            )
            scored.append((float(score), entry))

        scored.sort(key=lambda t: t[0], reverse=True)
        results = [entry for _, entry in scored[:limit]]
        top_scores = [f"{s:.4f}" for s, _ in scored[:limit]]
        logger.debug(
            "Recall complete: candidates=%d, returned=%d, top_scores=%s",
            len(rows),
            len(results),
            top_scores,
        )
        return results

    async def compact(self, messages: list[Message]) -> list[Message]:
        """Pass-through; compaction is handled by :func:`compact_messages`."""
        return messages

    async def clear(self) -> None:
        """Delete all stored memories."""
        self._ensure_open()
        logger.info("Clearing all stored memories")
        await self._db.execute("DELETE FROM memories")  # type: ignore[union-attr]
        await self._db.commit()  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_open(self) -> None:
        if self._db is None:
            raise SageMemoryError("Database not initialized. Call 'initialize()' first.")

    @staticmethod
    def _cosine_similarity(
        a: npt.NDArray[np.floating[Any]], b: npt.NDArray[np.floating[Any]]
    ) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

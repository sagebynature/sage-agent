"""SQLite-backed memory with vector similarity search."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import aiosqlite
import numpy as np
import numpy.typing as npt

from sage.exceptions import SageMemoryError
from sage.memory.base import MemoryEntry
from sage.memory.embedding import EmbeddingProtocol
from sage.models import Message
from sage.tracing import span

if TYPE_CHECKING:
    from sage.config import MemoryConfig

logger = logging.getLogger(__name__)


class SQLiteMemory:
    """SQLite-backed memory with cosine-similarity vector search.

    Call :meth:`initialize` before any other operation to create the
    database schema.

    When *config* is provided and ``config.vector_search`` is ``"auto"`` or
    ``"sqlite_vec"``, the backend attempts to load the ``sqlite-vec`` extension
    for O(log n) ANN search.  If the extension is unavailable the numpy O(n)
    path is used transparently.  Setting ``vector_search="numpy"`` forces the
    numpy path even when ``sqlite-vec`` is installed.
    """

    def __init__(
        self,
        path: str = "memory.db",
        *,
        embedding: EmbeddingProtocol,
        config: MemoryConfig | None = None,
    ) -> None:
        self._path = path
        self._embedding = embedding
        self._config = config
        self._db: aiosqlite.Connection | None = None
        self._vec_available: bool = False

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

        # Determine whether to attempt sqlite-vec setup
        vector_search = "auto"
        if self._config is not None:
            vector_search = self._config.vector_search

        if vector_search in ("auto", "sqlite_vec"):
            await self._try_enable_vec()

    async def _try_enable_vec(self) -> None:
        """Attempt to load the sqlite-vec extension and create the vec table.

        Failures are caught and logged at DEBUG level; the numpy fallback is
        used in that case.
        """
        try:
            # aiosqlite proxies enable_load_extension as a coroutine.
            await self._db.enable_load_extension(True)  # type: ignore[union-attr]
        except AttributeError:
            # Older aiosqlite versions may not proxy this method.
            import asyncio

            await asyncio.get_running_loop().run_in_executor(
                None,
                self._db._conn.enable_load_extension,  # type: ignore[union-attr]
                True,
            )
        except Exception:
            # SQLite compiled without SQLITE_ENABLE_LOAD_EXTENSION raises
            # OperationalError("not authorized") — fall through to numpy.
            logger.debug(
                "sqlite-vec unavailable (enable_load_extension not permitted), using numpy fallback"
            )
            return

        try:
            import sqlite_vec  # type: ignore[import-not-found]

            await self._db.load_extension(sqlite_vec.loadable_path())  # type: ignore[union-attr]

            # Probe the embedding dimension with a dummy embedding.
            probe = await self._embedding.embed(["probe"])
            dim = len(probe[0])

            await self._db.execute(  # type: ignore[union-attr]
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_vec
                USING vec0(embedding float[{dim}])
                """
            )
            await self._db.commit()  # type: ignore[union-attr]
            self._vec_available = True
            logger.debug("sqlite-vec ANN search enabled (dim=%d)", dim)
        except Exception as exc:
            logger.debug("sqlite-vec unavailable (%s), using numpy fallback", exc)
            self._vec_available = False

    async def close(self) -> None:
        """Close the database connection and wait for the worker thread."""
        if self._db is not None:
            thread = getattr(self._db, "_thread", None)
            logger.debug("Closing memory database connection")
            await self._db.close()
            if thread is not None:
                thread.join(timeout=2.0)
            self._db = None

    # ------------------------------------------------------------------
    # MemoryProtocol
    # ------------------------------------------------------------------

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store *content* with an embedding and return the memory ID."""
        self._ensure_open()

        async with span("memory.store", {"content_length": len(content)}):
            memory_id = uuid.uuid4().hex
            vectors = await self._embedding.embed([content])
            embedding_array = np.array(vectors[0], dtype=np.float32)
            embedding_blob = embedding_array.tobytes()
            meta_json = json.dumps(metadata or {})
            created_at = datetime.now(timezone.utc).isoformat()

            cursor = await self._db.execute(  # type: ignore[union-attr]
                "INSERT INTO memories (id, content, embedding, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
                (memory_id, content, embedding_blob, meta_json, created_at),
            )

            if self._vec_available:
                try:
                    import sqlite_vec  # type: ignore[import-not-found]

                    rowid = cursor.lastrowid
                    embedding_bytes = sqlite_vec.serialize_float32(embedding_array)
                    await self._db.execute(  # type: ignore[union-attr]
                        "INSERT INTO memory_vec(rowid, embedding) VALUES (?, ?)",
                        [rowid, embedding_bytes],
                    )
                except Exception as exc:
                    logger.warning(
                        "sqlite-vec insert failed (%s) — vec index may be stale; recall will use numpy",
                        exc,
                    )

            await self._db.commit()  # type: ignore[union-attr]
            logger.debug("Stored memory id=%s, content_preview=%.80s", memory_id, content)
            return memory_id

    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Return the top-*limit* memories ranked by cosine similarity."""
        self._ensure_open()
        logger.debug("Recalling memories: query_preview=%.80s, limit=%d", query, limit)

        async with span("memory.recall", {"query_length": len(query), "limit": limit}) as mem_span:
            query_vectors = await self._embedding.embed([query])
            query_embedding = query_vectors[0]

            if self._vec_available:
                results = await self._recall_vec(query_embedding, limit)
            else:
                results = await self._recall_numpy(query_embedding, limit)

            mem_span.set_attribute("result_count", len(results))
            return results

    async def _recall_numpy(self, query_embedding: list[float], limit: int) -> list[MemoryEntry]:
        """O(n) numpy cosine-similarity recall (original implementation)."""
        query_vec = np.array(query_embedding, dtype=np.float32)

        cursor = await self._db.execute(  # type: ignore[union-attr]
            "SELECT id, content, embedding, metadata, created_at FROM memories"
        )
        rows = list(await cursor.fetchall())

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
            "Recall complete (numpy): candidates=%d, returned=%d, top_scores=%s",
            len(rows),
            len(results),
            top_scores,
        )
        return results

    async def _recall_vec(self, query_embedding: list[float], limit: int) -> list[MemoryEntry]:
        """O(log n) ANN recall using sqlite-vec vec_distance_cosine."""
        import sqlite_vec  # type: ignore[import-not-found]

        query_array = np.array(query_embedding, dtype=np.float32)
        query_bytes = sqlite_vec.serialize_float32(query_array)

        rows = await self._db.execute_fetchall(  # type: ignore[union-attr]
            """
            SELECT m.id, m.content, m.metadata, m.created_at,
                   vec_distance_cosine(mv.embedding, ?) AS distance
            FROM memory_vec mv
            JOIN memories m ON m.rowid = mv.rowid
            ORDER BY distance ASC
            LIMIT ?
            """,
            [query_bytes, limit],
        )
        entries = [
            MemoryEntry(
                id=row[0],
                content=row[1],
                metadata=json.loads(row[2]) if row[2] else {},
                score=1.0 - float(row[4]),  # convert distance to similarity
                created_at=row[3],
            )
            for row in rows
        ]
        top_scores = [f"{e.score:.4f}" for e in entries]
        logger.debug(
            "Recall complete (sqlite-vec): returned=%d, top_scores=%s",
            len(entries),
            top_scores,
        )
        return entries

    async def compact(self, messages: list[Message]) -> list[Message]:
        """Pass-through; compaction is handled by :func:`compact_messages`."""
        return messages

    async def clear(self) -> None:
        """Delete all stored memories."""
        self._ensure_open()
        logger.info("Clearing all stored memories")
        await self._db.execute("DELETE FROM memories")  # type: ignore[union-attr]
        if self._vec_available:
            await self._db.execute("DELETE FROM memory_vec")  # type: ignore[union-attr]
        await self._db.commit()  # type: ignore[union-attr]

    async def get(self, memory_id: str) -> MemoryEntry | None:
        """Retrieve a single memory entry by *memory_id*, or None if not found."""
        self._ensure_open()
        cursor = await self._db.execute(  # type: ignore[union-attr]
            "SELECT id, content, metadata, created_at FROM memories WHERE id = ?",
            (memory_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return MemoryEntry(
            id=row[0],
            content=row[1],
            metadata=json.loads(row[2]) if row[2] else {},
            created_at=row[3],
        )

    async def list_entries(self, *, limit: int = 50, offset: int = 0) -> list[MemoryEntry]:
        """Return a paginated list of memory entries ordered by most-recently created."""
        self._ensure_open()
        cursor = await self._db.execute(  # type: ignore[union-attr]
            "SELECT id, content, metadata, created_at FROM memories ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [
            MemoryEntry(
                id=row[0],
                content=row[1],
                metadata=json.loads(row[2]) if row[2] else {},
                created_at=row[3],
            )
            for row in rows
        ]

    async def forget(self, memory_id: str) -> bool:
        """Delete the entry with *memory_id*. Return True if found and deleted, False if not found."""
        self._ensure_open()
        cursor = await self._db.execute(  # type: ignore[union-attr]
            "DELETE FROM memories WHERE id = ?",
            (memory_id,),
        )
        await self._db.commit()  # type: ignore[union-attr]
        return cursor.rowcount > 0

    async def count(self) -> int:
        """Return the total number of stored memory entries."""
        self._ensure_open()
        cursor = await self._db.execute(  # type: ignore[union-attr]
            "SELECT COUNT(*) FROM memories"
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def health_check(self) -> dict[str, Any]:
        """Return a health status dictionary with status, backend, count, and path."""
        self._ensure_open()
        entry_count = await self.count()
        return {
            "status": "ok",
            "backend": "sqlite",
            "count": entry_count,
            "path": self._path,
        }

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

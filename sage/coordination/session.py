"""Per-session isolated state container and lifecycle manager."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite
from pydantic import BaseModel, Field

from sage.models import Message


class SessionState(BaseModel):
    """In-memory state container for a single agent session.

    Each instance is fully isolated — mutable fields use ``default_factory``
    so that no state is shared across instances.

    Usage::

        state = SessionState(agent_name="researcher")
        state.add_message(Message(role="user", content="hello"))
        msgs = state.get_messages(limit=10)
    """

    session_id: str = Field(default_factory=lambda: uuid4().hex)
    agent_name: str
    created_at: float = Field(default_factory=time.time)
    messages: list[Message] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tool_results: dict[str, Any] = Field(default_factory=dict)

    def add_message(self, msg: Message) -> None:
        """Append a message to the conversation history."""
        self.messages.append(msg)

    def get_messages(self, limit: int | None = None) -> list[Message]:
        """Return conversation history, optionally capped to the latest *limit* entries."""
        if limit is None:
            return list(self.messages)
        return list(self.messages[-limit:])

    def set_metadata(self, key: str, value: Any) -> None:
        """Store an arbitrary key/value pair in session metadata."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Retrieve a metadata value, returning *default* if not present."""
        return self.metadata.get(key, default)

    def clear(self) -> None:
        """Reset messages and tool_results; metadata is preserved."""
        self.messages.clear()
        self.tool_results.clear()


class SessionManager:
    """In-memory manager for concurrent session lifecycle."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def create(
        self,
        agent_name: str,
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionState:
        """Create a new session. Auto-generates session_id if not provided."""
        sid = session_id if session_id is not None else uuid4().hex
        session = SessionState(
            session_id=sid,
            agent_name=agent_name,
            metadata=metadata or {},
        )
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> SessionState | None:
        """Retrieve session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self, *, agent_name: str | None = None) -> list[SessionState]:
        """List all sessions, optionally filtered by agent_name."""
        sessions = list(self._sessions.values())
        if agent_name is not None:
            sessions = [s for s in sessions if s.agent_name == agent_name]
        return sessions

    def destroy(self, session_id: str) -> bool:
        """Remove session. Returns True if found, False if not found."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def count(self) -> int:
        """Return number of active sessions."""
        return len(self._sessions)


class PersistentSessionManager:
    """In-memory SessionManager extended with SQLite-backed persistence.

    Composition over inheritance: wraps a :class:`SessionManager` so the
    original in-memory API is unchanged.  Call :meth:`initialize` once before
    any other operation to open the database and create the schema.
    """

    def __init__(self, db_path: str = "~/.sage/sessions.db") -> None:
        self._db_path = Path(db_path).expanduser()
        self._inner = SessionManager()
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                agent_name  TEXT NOT NULL,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL,
                metadata    TEXT DEFAULT '{}',
                messages    TEXT DEFAULT '[]',
                status      TEXT DEFAULT 'active'
            )
            """
        )
        await self._db.commit()

    def create(
        self,
        agent_name: str,
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionState:
        return self._inner.create(agent_name, session_id=session_id, metadata=metadata)

    def get(self, session_id: str) -> SessionState | None:
        return self._inner.get(session_id)

    def list_sessions(self, *, agent_name: str | None = None) -> list[SessionState]:
        return self._inner.list_sessions(agent_name=agent_name)

    def destroy(self, session_id: str) -> bool:
        return self._inner.destroy(session_id)

    def count(self) -> int:
        return self._inner.count()

    async def save(self, session_id: str) -> None:
        """Serialize in-memory session to SQLite (upsert).

        Raises :exc:`KeyError` if *session_id* is not in the in-memory cache.
        """
        assert self._db is not None, "Call initialize() before save()"
        state = self._inner.get(session_id)
        if state is None:
            raise KeyError(f"Session {session_id!r} not found in memory")

        messages_json = json.dumps([json.loads(msg.model_dump_json()) for msg in state.messages])
        metadata_json = json.dumps(state.metadata)
        now = time.time()

        await self._db.execute(
            """
            INSERT INTO sessions (id, agent_name, created_at, updated_at, metadata, messages, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            ON CONFLICT(id) DO UPDATE SET
                agent_name = excluded.agent_name,
                updated_at = excluded.updated_at,
                metadata   = excluded.metadata,
                messages   = excluded.messages,
                status     = excluded.status
            """,
            (
                state.session_id,
                state.agent_name,
                state.created_at,
                now,
                metadata_json,
                messages_json,
            ),
        )
        await self._db.commit()

    async def load(self, session_id: str) -> SessionState | None:
        """Deserialize a session from SQLite into the in-memory cache.

        Returns ``None`` if the session does not exist in the database.
        """
        assert self._db is not None, "Call initialize() before load()"

        async with self._db.execute(
            "SELECT id, agent_name, created_at, metadata, messages FROM sessions WHERE id = ?",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        sid, agent_name, created_at, metadata_json, messages_json = row
        metadata: dict[str, Any] = json.loads(metadata_json)
        raw_messages: list[dict[str, Any]] = json.loads(messages_json)
        messages = [Message.model_validate(m) for m in raw_messages]

        state = SessionState(
            session_id=sid,
            agent_name=agent_name,
            created_at=created_at,
            messages=messages,
            metadata=metadata,
        )
        self._inner._sessions[sid] = state
        return state

    async def list_persisted(self, agent_name: str | None = None) -> list[dict[str, Any]]:
        """Return metadata-only rows from SQLite (id, agent_name, created_at, updated_at, message_count, status).

        Full message payloads are not included; use :meth:`load` to hydrate a session.
        """
        assert self._db is not None, "Call initialize() before list_persisted()"

        if agent_name is not None:
            query = (
                "SELECT id, agent_name, created_at, updated_at, messages, status"
                " FROM sessions WHERE agent_name = ?"
            )
            params: tuple[Any, ...] = (agent_name,)
        else:
            query = "SELECT id, agent_name, created_at, updated_at, messages, status FROM sessions"
            params = ()

        results: list[dict[str, Any]] = []
        async with self._db.execute(query, params) as cursor:
            async for row in cursor:
                sid, aname, created_at, updated_at, messages_json, status = row
                raw: list[Any] = json.loads(messages_json)
                results.append(
                    {
                        "id": sid,
                        "agent_name": aname,
                        "created_at": created_at,
                        "updated_at": updated_at,
                        "message_count": len(raw),
                        "status": status,
                    }
                )
        return results

    async def delete(self, session_id: str) -> bool:
        """Remove session from SQLite and in-memory cache.

        Returns ``True`` if found in SQLite, ``False`` otherwise.
        """
        assert self._db is not None, "Call initialize() before delete()"

        async with self._db.execute(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            self._inner.destroy(session_id)
            return False

        await self._db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await self._db.commit()
        self._inner.destroy(session_id)
        return True

    async def fork(self, session_id: str, new_name: str | None = None) -> SessionState:
        """Copy a session into a new independent session with a fresh ID.

        Loads the source from SQLite if not already in memory.
        Raises :exc:`KeyError` if the source cannot be found anywhere.
        """
        assert self._db is not None, "Call initialize() before fork()"

        source = self._inner.get(session_id)
        if source is None:
            source = await self.load(session_id)
        if source is None:
            raise KeyError(f"Session {session_id!r} not found")

        new_id = uuid4().hex
        forked = SessionState(
            session_id=new_id,
            agent_name=new_name if new_name is not None else source.agent_name,
            created_at=time.time(),
            messages=list(source.messages),
            metadata=dict(source.metadata),
        )
        self._inner._sessions[new_id] = forked
        await self.save(new_id)
        return forked

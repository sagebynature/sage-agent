"""Per-session isolated state container and lifecycle manager."""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

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

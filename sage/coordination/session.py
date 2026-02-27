"""Per-session isolated state container."""

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

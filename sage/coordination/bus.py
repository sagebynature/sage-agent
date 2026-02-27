"""In-memory message bus for agent coordination."""

from collections import deque
import time
import logging
from sage.coordination.messages import MessageEnvelope

logger = logging.getLogger(__name__)


class MessageBus:
    """In-memory message bus with per-agent inboxes, TTL, idempotency, and dead letters.

    Thread-safe: NO (single-threaded asyncio model assumed).
    Not persisted: in-memory only.
    """

    def __init__(self, *, max_inbox_size: int = 100, ttl_seconds: float = 300.0):
        self._inboxes: dict[str, deque[MessageEnvelope]] = {}
        self._seen_ids: set[str] = set()  # for idempotency
        self._dead_letters: deque[MessageEnvelope] = deque(maxlen=100)
        self.max_inbox_size = max_inbox_size
        self.ttl_seconds = ttl_seconds

    def send(self, msg: MessageEnvelope) -> bool:
        """Deliver msg to recipient's inbox.

        Returns False if duplicate (same msg.id already seen — idempotency guard).
        Creates inbox if it doesn't exist yet.
        Drops oldest message if inbox at max_inbox_size.
        """
        if msg.id in self._seen_ids:
            logger.debug("Duplicate message %s rejected (idempotency guard)", msg.id)
            return False

        self._seen_ids.add(msg.id)

        recipient = msg.recipient
        if recipient not in self._inboxes:
            self._inboxes[recipient] = deque(maxlen=None)

        inbox = self._inboxes[recipient]
        if len(inbox) >= self.max_inbox_size:
            dropped = inbox.popleft()
            logger.debug("Inbox overflow for %r — dropped oldest message %s", recipient, dropped.id)

        inbox.append(msg)
        logger.debug("Delivered message %s to inbox %r", msg.id, recipient)
        return True

    def receive(self, agent_name: str, *, limit: int = 10) -> list[MessageEnvelope]:
        """Pop up to limit messages from agent's inbox.

        Skips expired messages (age > ttl_seconds), moves them to dead_letters.
        Returns only live (non-expired) messages.
        """
        inbox = self._inboxes.get(agent_name)
        if inbox is None:
            return []

        now = time.time()
        live: list[MessageEnvelope] = []

        while inbox and len(live) < limit:
            msg = inbox.popleft()
            age = now - msg.timestamp
            if age > self.ttl_seconds:
                logger.debug(
                    "Message %s expired (age=%.3fs, ttl=%.3fs) → dead letters",
                    msg.id,
                    age,
                    self.ttl_seconds,
                )
                self._dead_letters.append(msg)
            else:
                live.append(msg)

        return live

    def broadcast(self, msg: MessageEnvelope) -> int:
        """Send msg to ALL known inboxes (all registered agents).

        Sets recipient to "*" semantically (delivers a copy to each inbox).
        Returns delivery count (number of inboxes delivered to).
        Note: idempotency check is per-delivery (one send per inbox), not global.
        """
        agents = list(self._inboxes.keys())  # snapshot to avoid mutation during iteration
        if not agents:
            return 0

        count = 0
        for agent in agents:
            # Create a copy of the message with the specific recipient so each delivery
            # is independently tracked; we rebuild with a fresh id to avoid idempotency
            # collisions across agents.
            copy = msg.model_copy(
                update={"recipient": agent, "id": msg.id + f"__broadcast__{agent}"}
            )
            # Bypass the normal idempotency check for broadcast copies — deliver directly.
            inbox = self._inboxes[agent]
            if len(inbox) >= self.max_inbox_size:
                inbox.popleft()
            inbox.append(copy)
            count += 1
            logger.debug("Broadcast message %s delivered to %r", copy.id, agent)

        return count

    def peek(self, agent_name: str) -> int:
        """Count pending non-expired messages without consuming them."""
        inbox = self._inboxes.get(agent_name)
        if inbox is None:
            return 0

        now = time.time()
        count = sum(1 for msg in inbox if (now - msg.timestamp) <= self.ttl_seconds)
        return count

    def get_dead_letters(self, limit: int = 10) -> list[MessageEnvelope]:
        """Inspect undeliverable/expired messages (non-destructive)."""
        return list(self._dead_letters)[-limit:]

    def clear(self, agent_name: str | None = None) -> None:
        """Clear specific inbox (agent_name) or all inboxes (None)."""
        if agent_name is None:
            for inbox in self._inboxes.values():
                inbox.clear()
            logger.debug("Cleared all inboxes")
        else:
            _inbox = self._inboxes.get(agent_name)
            if _inbox is not None:
                _inbox.clear()
            logger.debug("Cleared inbox for %r", agent_name)

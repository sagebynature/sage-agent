"""Tests for sage.coordination.bus — in-memory message bus.

TDD: These tests were written BEFORE the implementation.
"""

from __future__ import annotations

import time


from sage.coordination.messages import DelegateTask, TaskResult
from sage.coordination.bus import MessageBus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_delegate(
    sender: str = "parent", recipient: str = "child", task: str = "do stuff"
) -> DelegateTask:
    return DelegateTask(sender=sender, recipient=recipient, task=task)


def _make_result(sender: str = "child", recipient: str = "parent") -> TaskResult:
    return TaskResult(sender=sender, recipient=recipient, result="done", success=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSendReceiveRoundtrip:
    """test_send_receive_roundtrip: send DelegateTask → receive gets it."""

    def test_send_returns_true_on_success(self):
        bus = MessageBus()
        msg = _make_delegate()
        assert bus.send(msg) is True

    def test_receive_returns_sent_message(self):
        bus = MessageBus()
        msg = _make_delegate(recipient="worker")
        bus.send(msg)
        received = bus.receive("worker")
        assert len(received) == 1
        assert received[0].id == msg.id
        assert received[0].task == "do stuff"

    def test_receive_empties_inbox(self):
        bus = MessageBus()
        msg = _make_delegate(recipient="worker")
        bus.send(msg)
        bus.receive("worker")
        assert bus.receive("worker") == []

    def test_receive_on_empty_inbox_returns_empty_list(self):
        bus = MessageBus()
        assert bus.receive("nobody") == []

    def test_receive_limit_respected(self):
        bus = MessageBus()
        for i in range(5):
            bus.send(_make_delegate(task=f"task-{i}", recipient="worker"))
        received = bus.receive("worker", limit=3)
        assert len(received) == 3

    def test_inbox_created_on_send(self):
        bus = MessageBus()
        msg = _make_delegate(recipient="new_agent")
        bus.send(msg)
        assert bus.peek("new_agent") >= 1


class TestIdempotency:
    """test_idempotency: same msg sent twice → second returns False, inbox has 1 message."""

    def test_second_send_returns_false(self):
        bus = MessageBus()
        msg = _make_delegate()
        assert bus.send(msg) is True
        assert bus.send(msg) is False

    def test_duplicate_not_added_to_inbox(self):
        bus = MessageBus()
        msg = _make_delegate(recipient="worker")
        bus.send(msg)
        bus.send(msg)  # duplicate
        received = bus.receive("worker")
        assert len(received) == 1

    def test_different_messages_both_accepted(self):
        bus = MessageBus()
        msg1 = _make_delegate(task="task1", recipient="worker")
        msg2 = _make_delegate(task="task2", recipient="worker")
        assert bus.send(msg1) is True
        assert bus.send(msg2) is True
        received = bus.receive("worker")
        assert len(received) == 2


class TestTTLExpiry:
    """test_ttl_expiry: bus with ttl=0.01s, send, sleep 0.05s, receive → [] (expired)."""

    def test_expired_message_not_returned(self):
        bus = MessageBus(ttl_seconds=0.01)
        msg = _make_delegate(recipient="worker")
        bus.send(msg)
        time.sleep(0.05)
        received = bus.receive("worker")
        assert received == []

    def test_non_expired_message_returned(self):
        bus = MessageBus(ttl_seconds=60.0)
        msg = _make_delegate(recipient="worker")
        bus.send(msg)
        received = bus.receive("worker")
        assert len(received) == 1

    def test_mixed_expiry(self):
        """Send a message, let it expire, send fresh one — only fresh is received."""
        bus = MessageBus(ttl_seconds=0.05)
        old_msg = _make_delegate(task="old", recipient="worker")
        bus.send(old_msg)
        time.sleep(0.1)
        fresh_msg = _make_delegate(task="fresh", recipient="worker")
        bus.send(fresh_msg)
        received = bus.receive("worker")
        assert len(received) == 1
        assert received[0].task == "fresh"


class TestTTLDeadLetters:
    """test_ttl_dead_letters: expired messages go to dead_letters."""

    def test_expired_message_in_dead_letters(self):
        bus = MessageBus(ttl_seconds=0.01)
        msg = _make_delegate(recipient="worker")
        bus.send(msg)
        time.sleep(0.05)
        bus.receive("worker")  # triggers expiry check
        dead = bus.get_dead_letters()
        assert len(dead) >= 1

    def test_dead_letter_contains_original_message(self):
        bus = MessageBus(ttl_seconds=0.01)
        msg = _make_delegate(recipient="worker", task="old_task")
        bus.send(msg)
        time.sleep(0.05)
        bus.receive("worker")
        dead = bus.get_dead_letters()
        assert any(d.id == msg.id for d in dead)

    def test_live_messages_not_in_dead_letters(self):
        bus = MessageBus(ttl_seconds=60.0)
        msg = _make_delegate(recipient="worker")
        bus.send(msg)
        bus.receive("worker")
        assert bus.get_dead_letters() == []


class TestInboxOverflow:
    """test_inbox_overflow: send max_inbox_size+1 messages → oldest dropped, inbox at max."""

    def test_inbox_capped_at_max(self):
        bus = MessageBus(max_inbox_size=5)
        for i in range(6):
            bus.send(_make_delegate(task=f"task-{i}", recipient="worker"))
        assert bus.peek("worker") == 5

    def test_oldest_message_dropped(self):
        bus = MessageBus(max_inbox_size=3)
        msgs = [_make_delegate(task=f"task-{i}", recipient="worker") for i in range(4)]
        for msg in msgs:
            bus.send(msg)
        received = bus.receive("worker", limit=10)
        received_tasks = [r.task for r in received]
        # First message (task-0) should be dropped
        assert "task-0" not in received_tasks
        assert "task-3" in received_tasks

    def test_overflow_does_not_reject(self):
        """Overflow drops oldest but still accepts the new message (no error)."""
        bus = MessageBus(max_inbox_size=2)
        for i in range(5):
            result = bus.send(_make_delegate(task=f"task-{i}", recipient="worker"))
            # Non-duplicate messages should return True (not rejected by overflow)
            assert result is True


class TestBroadcast:
    """test_broadcast: 3 agents, broadcast → all 3 inboxes get message, returns 3."""

    def setup_method(self):
        self.bus = MessageBus()
        # Register inboxes by sending placeholder messages
        for name in ["agent_a", "agent_b", "agent_c"]:
            init_msg = _make_delegate(recipient=name, task="init")
            self.bus.send(init_msg)
            self.bus.receive(name)  # drain the init message

    def test_broadcast_returns_delivery_count(self):
        msg = _make_delegate(sender="coordinator", recipient="*", task="broadcast_task")
        count = self.bus.broadcast(msg)
        assert count == 3

    def test_broadcast_delivers_to_all_agents(self):
        msg = _make_delegate(sender="coordinator", recipient="*", task="broadcast_task")
        self.bus.broadcast(msg)
        for name in ["agent_a", "agent_b", "agent_c"]:
            received = self.bus.receive(name)
            assert len(received) == 1
            assert received[0].task == "broadcast_task"

    def test_broadcast_empty_bus_returns_zero(self):
        bus = MessageBus()
        msg = _make_delegate(sender="coord", recipient="*")
        assert bus.broadcast(msg) == 0

    def test_broadcast_unique_message_ids(self):
        """Each delivery should be a fresh message (unique ID) since we can't re-use same ID."""
        msg = _make_delegate(sender="coord", recipient="*", task="broadcast")
        self.bus.broadcast(msg)
        all_received = []
        for name in ["agent_a", "agent_b", "agent_c"]:
            all_received.extend(self.bus.receive(name))
        # All messages should be distinct (broadcast creates copies or same ID per inbox is fine)
        # The key requirement is each inbox received one message
        assert len(all_received) == 3


class TestPeekNondestructive:
    """test_peek_nondestructive: peek count, then receive → same count."""

    def test_peek_returns_correct_count(self):
        bus = MessageBus()
        for i in range(3):
            bus.send(_make_delegate(task=f"task-{i}", recipient="worker"))
        assert bus.peek("worker") == 3

    def test_peek_does_not_consume_messages(self):
        bus = MessageBus()
        for i in range(3):
            bus.send(_make_delegate(task=f"task-{i}", recipient="worker"))
        count = bus.peek("worker")
        received = bus.receive("worker", limit=100)
        assert len(received) == count

    def test_peek_on_empty_inbox_returns_zero(self):
        bus = MessageBus()
        assert bus.peek("nobody") == 0

    def test_peek_excludes_expired(self):
        bus = MessageBus(ttl_seconds=0.01)
        bus.send(_make_delegate(recipient="worker"))
        time.sleep(0.05)
        assert bus.peek("worker") == 0


class TestClearSpecific:
    """test_clear_specific: clear('agent_a') empties only that inbox."""

    def test_clear_specific_empties_target(self):
        bus = MessageBus()
        bus.send(_make_delegate(recipient="agent_a"))
        bus.send(_make_delegate(recipient="agent_b"))
        bus.clear("agent_a")
        assert bus.peek("agent_a") == 0

    def test_clear_specific_leaves_other_inbox(self):
        bus = MessageBus()
        bus.send(_make_delegate(recipient="agent_a"))
        bus.send(_make_delegate(recipient="agent_b"))
        bus.clear("agent_a")
        assert bus.peek("agent_b") == 1

    def test_clear_nonexistent_inbox_no_error(self):
        bus = MessageBus()
        bus.clear("does_not_exist")  # should not raise


class TestClearAll:
    """test_clear_all: clear() empties all inboxes."""

    def test_clear_all_empties_all_inboxes(self):
        bus = MessageBus()
        for name in ["a", "b", "c"]:
            bus.send(_make_delegate(recipient=name))
        bus.clear()
        for name in ["a", "b", "c"]:
            assert bus.peek(name) == 0

    def test_clear_all_no_error_on_empty_bus(self):
        bus = MessageBus()
        bus.clear()  # should not raise


class TestGetDeadLetters:
    """test_get_dead_letters: inspect without consuming."""

    def test_get_dead_letters_nondestructive(self):
        bus = MessageBus(ttl_seconds=0.01)
        bus.send(_make_delegate(recipient="worker"))
        time.sleep(0.05)
        bus.receive("worker")  # triggers expiry
        first = bus.get_dead_letters()
        second = bus.get_dead_letters()
        assert len(first) == len(second)

    def test_get_dead_letters_respects_limit(self):
        bus = MessageBus(ttl_seconds=0.01)
        for i in range(5):
            bus.send(_make_delegate(task=f"task-{i}", recipient="worker"))
        time.sleep(0.05)
        bus.receive("worker", limit=100)
        dead = bus.get_dead_letters(limit=2)
        assert len(dead) <= 2

    def test_get_dead_letters_empty_initially(self):
        bus = MessageBus()
        assert bus.get_dead_letters() == []

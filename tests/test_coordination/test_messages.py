"""Tests for coordination message envelope models — Task 6."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sage.coordination.messages import (
    Ack,
    ContextPatch,
    ControlMessage,
    DelegateTask,
    TaskResult,
    parse_envelope,
)


class TestMessageEnvelopeBase:
    def test_base_fields_have_defaults(self) -> None:
        msg = DelegateTask(sender="a", recipient="b", task="do something")
        assert msg.id != ""
        assert msg.timestamp > 0
        assert msg.version == 1

    def test_id_is_unique_per_instance(self) -> None:
        m1 = DelegateTask(sender="a", recipient="b", task="t1")
        m2 = DelegateTask(sender="a", recipient="b", task="t2")
        assert m1.id != m2.id

    def test_frozen_model_rejects_mutation(self) -> None:
        msg = DelegateTask(sender="a", recipient="b", task="task")
        with pytest.raises((ValidationError, TypeError)):
            msg.sender = "c"  # type: ignore[misc]


class TestDelegateTask:
    def test_create_with_required_fields(self) -> None:
        msg = DelegateTask(sender="parent", recipient="child", task="research X")
        assert msg.type == "delegate_task"
        assert msg.task == "research X"
        assert msg.context == {}

    def test_create_with_context(self) -> None:
        msg = DelegateTask(sender="parent", recipient="child", task="t", context={"key": "val"})
        assert msg.context == {"key": "val"}

    def test_serialization_roundtrip(self) -> None:
        msg = DelegateTask(sender="parent", recipient="child", task="research")
        data = msg.model_dump()
        parsed = parse_envelope(data)
        assert isinstance(parsed, DelegateTask)
        assert parsed.task == "research"
        assert parsed.sender == "parent"


class TestTaskResult:
    def test_create_success(self) -> None:
        msg = TaskResult(sender="child", recipient="parent", result="done", success=True)
        assert msg.type == "task_result"
        assert msg.success is True
        assert msg.error is None

    def test_create_with_error(self) -> None:
        msg = TaskResult(
            sender="child", recipient="parent", result="", success=False, error="timeout"
        )
        assert msg.error == "timeout"

    def test_serialization_roundtrip(self) -> None:
        msg = TaskResult(sender="child", recipient="parent", result="ok", success=True)
        data = msg.model_dump()
        parsed = parse_envelope(data)
        assert isinstance(parsed, TaskResult)
        assert parsed.result == "ok"


class TestAck:
    def test_create(self) -> None:
        msg = Ack(sender="child", recipient="parent", ref_id="abc123")
        assert msg.type == "ack"
        assert msg.ref_id == "abc123"

    def test_serialization_roundtrip(self) -> None:
        msg = Ack(sender="child", recipient="parent", ref_id="xyz")
        data = msg.model_dump()
        parsed = parse_envelope(data)
        assert isinstance(parsed, Ack)
        assert parsed.ref_id == "xyz"


class TestContextPatch:
    def test_create_set_operation(self) -> None:
        msg = ContextPatch(sender="a", recipient="b", key="foo", value=42)
        assert msg.type == "context_patch"
        assert msg.operation == "set"
        assert msg.value == 42

    def test_create_delete_operation(self) -> None:
        msg = ContextPatch(sender="a", recipient="b", key="foo", value=None, operation="delete")
        assert msg.operation == "delete"

    def test_serialization_roundtrip(self) -> None:
        msg = ContextPatch(sender="a", recipient="b", key="k", value=99)
        data = msg.model_dump()
        parsed = parse_envelope(data)
        assert isinstance(parsed, ContextPatch)
        assert parsed.key == "k"
        assert parsed.value == 99


class TestControlMessage:
    def test_create_pause(self) -> None:
        msg = ControlMessage(sender="a", recipient="b", command="pause")
        assert msg.type == "control"
        assert msg.command == "pause"

    def test_create_resume(self) -> None:
        msg = ControlMessage(sender="a", recipient="b", command="resume")
        assert msg.command == "resume"

    def test_create_cancel(self) -> None:
        msg = ControlMessage(sender="a", recipient="b", command="cancel")
        assert msg.command == "cancel"

    def test_serialization_roundtrip(self) -> None:
        msg = ControlMessage(sender="a", recipient="b", command="cancel")
        data = msg.model_dump()
        parsed = parse_envelope(data)
        assert isinstance(parsed, ControlMessage)
        assert parsed.command == "cancel"


class TestParseEnvelope:
    def test_invalid_type_raises_error(self) -> None:
        data = {
            "id": "abc",
            "type": "unknown_type",
            "sender": "a",
            "recipient": "b",
            "timestamp": 1.0,
            "version": 1,
        }
        with pytest.raises((ValueError, ValidationError)):
            parse_envelope(data)

    def test_broadcast_recipient(self) -> None:
        msg = DelegateTask(sender="parent", recipient="*", task="broadcast")
        data = msg.model_dump()
        parsed = parse_envelope(data)
        assert parsed.recipient == "*"

    def test_all_five_types_parse_correctly(self) -> None:
        messages = [
            DelegateTask(sender="p", recipient="c", task="t"),
            TaskResult(sender="c", recipient="p", result="r", success=True),
            Ack(sender="c", recipient="p", ref_id="ref1"),
            ContextPatch(sender="a", recipient="b", key="k", value="v"),
            ControlMessage(sender="a", recipient="b", command="pause"),
        ]
        for msg in messages:
            data = msg.model_dump()
            parsed = parse_envelope(data)
            assert type(parsed).__name__ == type(msg).__name__

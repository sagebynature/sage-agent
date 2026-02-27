"""Typed message envelope models for multi-agent coordination."""

from __future__ import annotations

import time
from typing import Annotated, Any, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class MessageEnvelope(BaseModel):
    """Base class for all coordination message envelopes."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: uuid4().hex)
    type: str
    sender: str
    recipient: str
    timestamp: float = Field(default_factory=time.time)
    version: int = 1


class DelegateTask(MessageEnvelope):
    """Delegate a task from one agent to another."""

    type: Literal["delegate_task"] = "delegate_task"
    task: str
    context: dict[str, Any] = Field(default_factory=dict)


class TaskResult(MessageEnvelope):
    """Report the result of a delegated task."""

    type: Literal["task_result"] = "task_result"
    result: str
    success: bool
    error: str | None = None


class ContextPatch(MessageEnvelope):
    """Patch a shared context value."""

    type: Literal["context_patch"] = "context_patch"
    key: str
    value: Any
    operation: Literal["set", "delete"] = "set"


class Ack(MessageEnvelope):
    """Acknowledge receipt of a message."""

    type: Literal["ack"] = "ack"
    ref_id: str


class ControlMessage(MessageEnvelope):
    """Send a control command to an agent."""

    type: Literal["control"] = "control"
    command: Literal["pause", "resume", "cancel"]


CoordinationMessage = Union[DelegateTask, TaskResult, ContextPatch, Ack, ControlMessage]

# Annotated union for discriminated parsing on the "type" field
_AnnotatedCoordinationMessage = Annotated[
    CoordinationMessage,
    Field(discriminator="type"),
]


def parse_envelope(data: dict[str, Any]) -> CoordinationMessage:
    """Parse a dict into the appropriate CoordinationMessage subtype.

    Uses Pydantic's discriminated union on the "type" field.

    Raises:
        ValueError: If the "type" field is missing or not recognised.
        ValidationError: If the data does not match the expected schema.
    """
    from pydantic import TypeAdapter

    adapter: TypeAdapter[CoordinationMessage] = TypeAdapter(_AnnotatedCoordinationMessage)
    return adapter.validate_python(data)

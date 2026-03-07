"""Canonical event telemetry for agent lifecycle observability."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from sage.hooks.builtin.credential_scrubber import scrub_text
from sage.models import Usage

logger = logging.getLogger(__name__)

_MAX_STRING_LENGTH = 5000
_MAX_DEPTH = 6
_REDACTED_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
}


class UsageSnapshot(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    reasoning_tokens: int = 0
    cost: float = 0.0


class ErrorSnapshot(BaseModel):
    type: str
    message: str
    retryable: bool = False
    provider_code: str | None = None


class EventEnvelope(BaseModel):
    version: int = 1
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    event_name: str
    category: str
    phase: Literal["start", "delta", "complete", "fail", "cancel", "point"] = "point"
    timestamp: float = Field(default_factory=time.time)
    agent_name: str
    agent_path: list[str] = Field(default_factory=list)
    run_id: str
    turn_id: str | None = None
    turn_index: int | None = None
    session_id: str | None = None
    originating_session_id: str | None = None
    parent_event_id: str | None = None
    trigger_event_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    status: Literal["ok", "error", "cancelled", "skipped"] | None = None
    duration_ms: float | None = None
    usage: UsageSnapshot | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    error: ErrorSnapshot | None = None


class PublishResult(BaseModel):
    accepted: bool = True
    backend: str = "memory"
    message: str | None = None


class EventPublisher(Protocol):
    async def publish(self, envelope: EventEnvelope) -> PublishResult: ...


class NoOpEventPublisher:
    async def publish(self, envelope: EventEnvelope) -> PublishResult:  # noqa: ARG002
        return PublishResult(accepted=True, backend="noop")


class InMemoryEventPublisher:
    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []

    async def publish(self, envelope: EventEnvelope) -> PublishResult:
        self.events.append(envelope)
        return PublishResult(accepted=True, backend="memory")


class EventSink(Protocol):
    async def write(self, envelope: EventEnvelope) -> None: ...


class LoggingEventSink:
    def __init__(self, logger_name: str = "sage.telemetry.sink") -> None:
        self._logger = logging.getLogger(logger_name)

    async def write(self, envelope: EventEnvelope) -> None:
        self._logger.debug(
            "event=%s phase=%s agent=%s run=%s status=%s",
            envelope.event_name,
            envelope.phase,
            envelope.agent_name,
            envelope.run_id,
            envelope.status,
        )


class TelemetryRecorder(Protocol):
    async def record(self, envelope: EventEnvelope, data: dict[str, Any]) -> EventEnvelope: ...


class DefaultTelemetryRecorder:
    """Records every lifecycle event and fans out to sinks/publisher."""

    def __init__(
        self,
        *,
        sinks: list[EventSink] | None = None,
        publisher: EventPublisher | None = None,
    ) -> None:
        self.events: list[EventEnvelope] = []
        self._sinks = sinks or []
        self._publisher = publisher

    async def record(self, envelope: EventEnvelope, data: dict[str, Any]) -> EventEnvelope:
        materialized = envelope.model_copy(update={"payload": sanitize_payload(data)})
        self.events.append(materialized)

        if self._publisher is not None:
            try:
                await self._publisher.publish(materialized)
            except Exception as exc:  # pragma: no cover - defensive isolation
                logger.warning("Telemetry publisher failed for %s: %s", envelope.event_name, exc)

        for sink in self._sinks:
            try:
                await sink.write(materialized)
            except Exception as exc:  # pragma: no cover - defensive isolation
                logger.warning("Telemetry sink failed for %s: %s", envelope.event_name, exc)

        return materialized


def usage_to_snapshot(usage: Usage | None) -> UsageSnapshot | None:
    if usage is None:
        return None
    return UsageSnapshot(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_creation_tokens=usage.cache_creation_tokens,
        reasoning_tokens=usage.reasoning_tokens,
        cost=usage.cost,
    )


def error_to_snapshot(exc: BaseException, *, retryable: bool = False) -> ErrorSnapshot:
    return ErrorSnapshot(
        type=type(exc).__name__,
        message=str(exc),
        retryable=retryable,
    )


def sanitize_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): _sanitize_value(value, depth=0, key_hint=str(key))
        for key, value in data.items()
        if key != "_event_envelope"
    }


def _sanitize_value(value: Any, *, depth: int, key_hint: str | None = None) -> Any:
    if depth >= _MAX_DEPTH:
        return "[max-depth]"

    if key_hint and key_hint.lower() in _REDACTED_KEYS:
        return "***REDACTED***"

    if value is None or isinstance(value, bool | int | float):
        return value

    if isinstance(value, str):
        text = scrub_text(value)
        if len(text) > _MAX_STRING_LENGTH:
            return text[:_MAX_STRING_LENGTH] + "...[truncated]"
        return text

    if isinstance(value, BaseModel):
        exclude: set[str] = set()
        model_fields = getattr(value.__class__, "model_fields", {})
        if "raw_response" in model_fields:
            exclude.add("raw_response")
        dumped = value.model_dump(exclude=exclude or None)
        return _sanitize_value(dumped, depth=depth + 1)

    if isinstance(value, dict):
        return {
            str(k): _sanitize_value(v, depth=depth + 1, key_hint=str(k)) for k, v in value.items()
        }

    if isinstance(value, list | tuple | set):
        return [_sanitize_value(v, depth=depth + 1) for v in value]

    if hasattr(value, "value") and hasattr(value, "name"):
        return getattr(value, "value")

    return scrub_text(str(value))


@dataclass(slots=True)
class ExecutionContext:
    run_id: str
    session_id: str | None
    originating_session_id: str | None
    agent_path: list[str] = field(default_factory=list)
    delegation_depth: int = 0
    current_turn: int | None = None
    current_turn_id: str | None = None
    current_event_id: str | None = None


_execution_context_var: ContextVar[ExecutionContext | None] = ContextVar(
    "sage_execution_context",
    default=None,
)


def get_execution_context() -> ExecutionContext | None:
    return _execution_context_var.get()


@contextmanager
def bind_execution_context(ctx: ExecutionContext):
    token = _execution_context_var.set(ctx)
    try:
        yield ctx
    finally:
        _execution_context_var.reset(token)


def root_execution_context(
    *,
    agent_name: str,
    session_id: str | None = None,
    originating_session_id: str | None = None,
) -> ExecutionContext:
    effective_session_id = session_id or uuid4().hex
    effective_origin = originating_session_id or effective_session_id
    return ExecutionContext(
        run_id=uuid4().hex,
        session_id=effective_session_id,
        originating_session_id=effective_origin,
        agent_path=[agent_name],
        delegation_depth=0,
    )


def child_execution_context(
    parent: ExecutionContext,
    *,
    agent_name: str,
    session_id: str | None = None,
    new_run_id: bool = False,
) -> ExecutionContext:
    return ExecutionContext(
        run_id=uuid4().hex if new_run_id else parent.run_id,
        session_id=session_id or uuid4().hex,
        originating_session_id=parent.originating_session_id or parent.session_id,
        agent_path=[*parent.agent_path, agent_name],
        delegation_depth=parent.delegation_depth + 1,
        current_turn=parent.current_turn,
        current_turn_id=parent.current_turn_id,
        current_event_id=parent.current_event_id,
    )


def with_turn_context(ctx: ExecutionContext, *, turn: int) -> ExecutionContext:
    return replace(
        ctx,
        current_turn=turn,
        current_turn_id=f"{ctx.run_id}:turn:{turn}",
    )


def with_event_context(ctx: ExecutionContext, *, event_id: str) -> ExecutionContext:
    return replace(ctx, current_event_id=event_id)


async def maybe_await(
    func: Callable[[EventEnvelope], Awaitable[None]] | None, envelope: EventEnvelope
) -> None:
    if func is None:
        return
    await func(envelope)

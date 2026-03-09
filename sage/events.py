"""Typed event dataclasses for the Sage agent lifecycle.

Each dataclass corresponds to one agent lifecycle point.  The
:data:`EVENT_TYPE_MAP` maps each event class to its underlying
:class:`~sage.hooks.base.HookEvent`, and :func:`from_hook_data` constructs a
typed instance from the raw ``dict`` emitted by the agent.

Usage::

    from sage.events import ToolStarted

    async def my_handler(e: ToolStarted) -> None:
        print(f"tool started: {e.name}")

    agent.on(ToolStarted, my_handler)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

from sage.hooks.base import HookEvent
from sage.models import ComplexityScore

E = TypeVar("E")


# ---------------------------------------------------------------------------
# Typed event dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ToolStarted:
    """Emitted just before a tool is dispatched."""

    name: str
    arguments: dict[str, Any]
    turn: int
    call_id: str | None = None
    run_id: str | None = None
    session_id: str | None = None
    originating_session_id: str | None = None
    agent_path: list[str] | None = None
    event_id: str | None = None


@dataclass
class ToolCompleted:
    """Emitted after a tool dispatch returns."""

    name: str
    result: str
    duration_ms: float
    call_id: str | None = None
    error: str | None = None
    run_id: str | None = None
    session_id: str | None = None
    originating_session_id: str | None = None
    agent_path: list[str] | None = None
    event_id: str | None = None


@dataclass
class LLMTurnStarted:
    """Emitted at the start of each LLM call."""

    turn: int
    model: str
    n_messages: int
    complexity: ComplexityScore | None = None
    run_id: str | None = None
    session_id: str | None = None
    originating_session_id: str | None = None
    agent_path: list[str] | None = None
    event_id: str | None = None


@dataclass
class LLMTurnCompleted:
    """Emitted after an LLM call returns."""

    turn: int
    usage: Any  # sage.models.Usage
    n_tool_calls: int
    model: str = ""
    complexity: ComplexityScore | None = None
    run_id: str | None = None
    session_id: str | None = None
    originating_session_id: str | None = None
    agent_path: list[str] | None = None
    event_id: str | None = None


@dataclass
class DelegationStarted:
    """Emitted when the agent is about to delegate to a subagent."""

    target: str
    task: str
    delegation_id: str | None = None
    run_id: str | None = None
    session_id: str | None = None
    originating_session_id: str | None = None
    agent_path: list[str] | None = None
    event_id: str | None = None


@dataclass
class DelegationCompleted:
    """Emitted after a subagent delegation returns."""

    target: str
    result: str
    duration_ms: float = 0.0
    delegation_id: str | None = None
    run_id: str | None = None
    session_id: str | None = None
    originating_session_id: str | None = None
    agent_path: list[str] | None = None
    event_id: str | None = None


@dataclass
class LLMStreamDelta:
    """Emitted for each text chunk during streaming."""

    delta: str
    turn: int
    run_id: str | None = None
    session_id: str | None = None
    originating_session_id: str | None = None
    agent_path: list[str] | None = None
    event_id: str | None = None


@dataclass
class BackgroundTaskCompleted:
    """Emitted when a background agent task finishes (success, failure, or cancellation)."""

    task_id: str
    agent_name: str
    status: str
    result: str | None
    error: str | None
    session_id: str | None = None
    originating_session_id: str | None = None
    run_id: str | None = None
    agent_path: list[str] | None = None
    event_id: str | None = None


# ---------------------------------------------------------------------------
# Mapping: event class → HookEvent
# ---------------------------------------------------------------------------

#: Maps each typed event class to its corresponding :class:`HookEvent`.
EVENT_TYPE_MAP: dict[type, HookEvent] = {
    ToolStarted: HookEvent.PRE_TOOL_EXECUTE,
    ToolCompleted: HookEvent.POST_TOOL_EXECUTE,
    LLMTurnStarted: HookEvent.PRE_LLM_CALL,
    LLMTurnCompleted: HookEvent.POST_LLM_CALL,
    DelegationStarted: HookEvent.ON_DELEGATION,
    DelegationCompleted: HookEvent.ON_DELEGATION_COMPLETE,
    LLMStreamDelta: HookEvent.ON_LLM_STREAM_DELTA,
    BackgroundTaskCompleted: HookEvent.BACKGROUND_TASK_COMPLETED,
}


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

_FACTORIES: dict[type, Any] = {
    ToolStarted: lambda d: ToolStarted(
        name=d.get("tool_name", ""),
        arguments=d.get("arguments", {}),
        turn=d.get("turn", 0),
        call_id=d.get("tool_call_id"),
        run_id=d.get("run_id"),
        session_id=d.get("session_id"),
        originating_session_id=d.get("originating_session_id"),
        agent_path=d.get("agent_path"),
        event_id=d.get("event_id"),
    ),
    ToolCompleted: lambda d: ToolCompleted(
        name=d.get("tool_name", ""),
        result=d.get("result", ""),
        duration_ms=d.get("duration_ms", 0.0),
        call_id=d.get("tool_call_id"),
        error=d.get("error"),
        run_id=d.get("run_id"),
        session_id=d.get("session_id"),
        originating_session_id=d.get("originating_session_id"),
        agent_path=d.get("agent_path"),
        event_id=d.get("event_id"),
    ),
    LLMTurnStarted: lambda d: LLMTurnStarted(
        turn=d.get("turn", 0),
        model=d.get("model", ""),
        n_messages=len(d.get("messages", [])),
        complexity=(
            d.get("complexity")
            if isinstance(d.get("complexity"), ComplexityScore)
            else ComplexityScore.model_validate(d["complexity"])
            if d.get("complexity") is not None
            else None
        ),
        run_id=d.get("run_id"),
        session_id=d.get("session_id"),
        originating_session_id=d.get("originating_session_id"),
        agent_path=d.get("agent_path"),
        event_id=d.get("event_id"),
    ),
    LLMTurnCompleted: lambda d: LLMTurnCompleted(
        turn=d.get("turn", 0),
        usage=d.get("usage"),
        n_tool_calls=d.get("n_tool_calls", 0),
        model=d.get("model", ""),
        complexity=(
            d.get("complexity")
            if isinstance(d.get("complexity"), ComplexityScore)
            else ComplexityScore.model_validate(d["complexity"])
            if d.get("complexity") is not None
            else None
        ),
        run_id=d.get("run_id"),
        session_id=d.get("session_id"),
        originating_session_id=d.get("originating_session_id"),
        agent_path=d.get("agent_path"),
        event_id=d.get("event_id"),
    ),
    DelegationStarted: lambda d: DelegationStarted(
        target=d.get("target", ""),
        task=d.get("input", ""),
        delegation_id=d.get("delegation_id"),
        run_id=d.get("run_id"),
        session_id=d.get("session_id"),
        originating_session_id=d.get("originating_session_id"),
        agent_path=d.get("agent_path"),
        event_id=d.get("event_id"),
    ),
    DelegationCompleted: lambda d: DelegationCompleted(
        target=d.get("target", ""),
        result=d.get("result", ""),
        duration_ms=d.get("duration_ms", 0.0),
        delegation_id=d.get("delegation_id"),
        run_id=d.get("run_id"),
        session_id=d.get("session_id"),
        originating_session_id=d.get("originating_session_id"),
        agent_path=d.get("agent_path"),
        event_id=d.get("event_id"),
    ),
    LLMStreamDelta: lambda d: LLMStreamDelta(
        delta=d.get("delta", ""),
        turn=d.get("turn", 0),
        run_id=d.get("run_id"),
        session_id=d.get("session_id"),
        originating_session_id=d.get("originating_session_id"),
        agent_path=d.get("agent_path"),
        event_id=d.get("event_id"),
    ),
    BackgroundTaskCompleted: lambda d: BackgroundTaskCompleted(
        task_id=d.get("task_id", ""),
        agent_name=d.get("agent_name", ""),
        status=d.get("status", ""),
        result=d.get("result"),
        error=d.get("error"),
        session_id=d.get("session_id"),
        originating_session_id=d.get("originating_session_id"),
        run_id=d.get("run_id"),
        agent_path=d.get("agent_path"),
        event_id=d.get("event_id"),
    ),
}


def from_hook_data(event_class: type[E], data: dict[str, Any]) -> E:
    """Construct a typed event instance from a raw hook data dict.

    Args:
        event_class: One of the typed event dataclasses in this module.
        data: The raw ``dict`` emitted by the agent hook system.

    Returns:
        A populated instance of *event_class*.

    Raises:
        KeyError: If *event_class* is not a known event type.
    """
    factory = _FACTORIES[event_class]
    return factory(data)

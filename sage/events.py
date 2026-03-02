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


@dataclass
class ToolCompleted:
    """Emitted after a tool dispatch returns."""

    name: str
    result: str
    duration_ms: float


@dataclass
class LLMTurnStarted:
    """Emitted at the start of each LLM call."""

    turn: int
    model: str
    n_messages: int


@dataclass
class LLMTurnCompleted:
    """Emitted after an LLM call returns."""

    turn: int
    usage: Any  # sage.models.Usage
    n_tool_calls: int


@dataclass
class DelegationStarted:
    """Emitted when the agent is about to delegate to a subagent."""

    target: str
    task: str


@dataclass
class DelegationCompleted:
    """Emitted after a subagent delegation returns."""

    target: str
    result: str


@dataclass
class LLMStreamDelta:
    """Emitted for each text chunk during streaming."""

    delta: str
    turn: int


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
}


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

_FACTORIES: dict[type, Any] = {
    ToolStarted: lambda d: ToolStarted(
        name=d.get("tool_name", ""),
        arguments=d.get("arguments", {}),
        turn=d.get("turn", 0),
    ),
    ToolCompleted: lambda d: ToolCompleted(
        name=d.get("tool_name", ""),
        result=d.get("result", ""),
        duration_ms=d.get("duration_ms", 0.0),
    ),
    LLMTurnStarted: lambda d: LLMTurnStarted(
        turn=d.get("turn", 0),
        model=d.get("model", ""),
        n_messages=len(d.get("messages", [])),
    ),
    LLMTurnCompleted: lambda d: LLMTurnCompleted(
        turn=d.get("turn", 0),
        usage=d.get("usage"),
        n_tool_calls=d.get("n_tool_calls", 0),
    ),
    DelegationStarted: lambda d: DelegationStarted(
        target=d.get("target", ""),
        task=d.get("input", ""),
    ),
    DelegationCompleted: lambda d: DelegationCompleted(
        target=d.get("target", ""),
        result=d.get("result", ""),
    ),
    LLMStreamDelta: lambda d: LLMStreamDelta(
        delta=d.get("delta", ""),
        turn=d.get("turn", 0),
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
    return factory(data)  # type: ignore[return-value]

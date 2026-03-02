"""Output writers for Sage CLI — JSONL, plain text, quiet, and verbose modes."""

from __future__ import annotations

import json
import sys
from typing import IO, TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sage.agent import Agent


@runtime_checkable
class OutputWriter(Protocol):
    """Protocol for CLI output writers.

    All writers must be safe to call from async contexts via normal
    synchronous calls — they do *not* need to be awaited.
    """

    def write_event(self, event: str, data: dict[str, object]) -> None:
        """Emit a structured lifecycle event."""
        ...

    def write_result(self, result: str) -> None:
        """Emit the final agent result."""
        ...

    def close(self) -> None:
        """Flush and close the underlying stream (if applicable)."""
        ...


class JSONLWriter:
    """Writes newline-delimited JSON (JSONL) to *stream*.

    Each call produces one line of the form::

        {"event": "<event>", "data": {...}}

    The final result is emitted as::

        {"event": "result", "data": {"output": "<result>"}}
    """

    def __init__(self, stream: IO[str] = sys.stdout) -> None:
        self._stream = stream

    def write_event(self, event: str, data: dict[str, object]) -> None:
        line = json.dumps({"event": event, "data": data}, ensure_ascii=False)
        self._stream.write(line + "\n")
        self._stream.flush()

    def write_result(self, result: str) -> None:
        self.write_event("result", {"output": result})

    def close(self) -> None:
        self._stream.flush()


class TextWriter:
    """Prints the final result as plain text (default / human-readable mode).

    Lifecycle events are silently discarded — only the result is printed,
    matching the existing ``sage agent run`` behaviour.
    """

    def __init__(self, stream: IO[str] = sys.stdout) -> None:
        self._stream = stream

    def write_event(self, event: str, data: dict[str, object]) -> None:  # noqa: ARG002
        pass  # Intentionally silent — events not shown in text mode.

    def write_result(self, result: str) -> None:
        self._stream.write(result + "\n")
        self._stream.flush()

    def close(self) -> None:
        self._stream.flush()


class QuietWriter:
    """Suppresses all output.

    Useful when the caller only cares about the exit code (e.g. smoke
    tests, health checks).
    """

    def write_event(self, event: str, data: dict[str, object]) -> None:  # noqa: ARG002
        pass

    def write_result(self, result: str) -> None:  # noqa: ARG002
        pass

    def close(self) -> None:
        pass


def make_writer(mode: str) -> OutputWriter:
    """Factory: return the appropriate :class:`OutputWriter` for *mode*.

    Args:
        mode: One of ``"text"``, ``"jsonl"``, or ``"quiet"``.

    Returns:
        An :class:`OutputWriter` instance.

    Raises:
        ValueError: If *mode* is not recognised.
    """
    match mode:
        case "jsonl":
            return JSONLWriter()
        case "quiet":
            return QuietWriter()
        case "text":
            return TextWriter()
        case _:
            raise ValueError(f"Unknown output mode: {mode!r}. Choose text, jsonl, or quiet.")


class VerboseWriter:
    """Prints formatted live agent events to stderr using Rich.

    Output goes to ``stderr`` so it does not pollute stdout (which carries the
    final result in text / JSONL mode).

    Example output::

        ◆ turn 1  model=claude-sonnet-4-6  msgs=3
        → tool: shell  cmd='ls -la'
        ✓ shell  (42ms)  → 'total 48...'
        ↳ delegate → researcher  'find papers on X'
        ✓ researcher  → 'Found 3 papers...'

    Call :meth:`attach` with an :class:`~sage.agent.Agent` instance to wire
    all subscriptions in one shot.
    """

    def __init__(self) -> None:
        from rich.console import Console

        self._console = Console(stderr=True)

    def attach(self, agent: "Agent") -> None:
        """Subscribe all verbose event handlers to *agent*."""
        from sage.events import (
            DelegationCompleted,
            DelegationStarted,
            LLMTurnStarted,
            ToolCompleted,
            ToolStarted,
        )

        agent.on(LLMTurnStarted, self._on_turn_started)
        agent.on(ToolStarted, self._on_tool_started)
        agent.on(ToolCompleted, self._on_tool_completed)
        agent.on(DelegationStarted, self._on_delegation_started)
        agent.on(DelegationCompleted, self._on_delegation_completed)

    async def _on_turn_started(self, e: Any) -> None:
        self._console.print(
            f"  [bold cyan]◆[/bold cyan] turn {e.turn + 1}  model={e.model}  msgs={e.n_messages}",
        )

    async def _on_tool_started(self, e: Any) -> None:
        args_preview = _fmt_args_brief(e.arguments)
        suffix = f"  {args_preview}" if args_preview else ""
        self._console.print(f"  [bold yellow]→[/bold yellow] tool: {e.name}{suffix}")

    async def _on_tool_completed(self, e: Any) -> None:
        result_preview = str(e.result)[:60].replace("\n", " ")
        self._console.print(
            f"  [bold green]✓[/bold green] {e.name}  ({e.duration_ms:.0f}ms)  → '{result_preview}'"
        )

    async def _on_delegation_started(self, e: Any) -> None:
        task_preview = e.task[:60].replace("\n", " ")
        self._console.print(
            f"  [bold magenta]↳[/bold magenta] delegate → {e.target}  '{task_preview}'"
        )

    async def _on_delegation_completed(self, e: Any) -> None:
        result_preview = str(e.result)[:60].replace("\n", " ")
        self._console.print(f"  [bold green]✓[/bold green] {e.target}  → '{result_preview}'")

    # OutputWriter protocol stubs — VerboseWriter is used alongside a TextWriter,
    # so these are intentional no-ops.
    def write_event(self, event: str, data: dict[str, object]) -> None:  # noqa: ARG002
        pass

    def write_result(self, result: str) -> None:  # noqa: ARG002
        pass

    def close(self) -> None:
        pass


def _fmt_args_brief(arguments: dict[str, Any]) -> str:
    """Return a short single-line summary of tool arguments."""
    if not arguments:
        return ""
    parts: list[str] = []
    for k, v in list(arguments.items())[:2]:
        val_str = str(v)
        if len(val_str) > 25:
            val_str = val_str[:25] + "…"
        parts.append(f"{k}={val_str!r}")
    if len(arguments) > 2:
        parts.append("…")
    return "  ".join(parts)

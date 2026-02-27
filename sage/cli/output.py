"""Output writers for Sage CLI — JSONL, plain text, and quiet modes."""

from __future__ import annotations

import json
import sys
from typing import IO, Protocol, runtime_checkable


@runtime_checkable
class OutputWriter(Protocol):
    """Protocol for CLI output writers.

    All writers must be safe to call from async contexts via normal
    synchronous calls — they do *not* need to be awaited.
    """

    def write_event(self, event: str, data: dict) -> None:
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

    def write_event(self, event: str, data: dict) -> None:
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

    def write_event(self, event: str, data: dict) -> None:  # noqa: ARG002
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

    def write_event(self, event: str, data: dict) -> None:  # noqa: ARG002
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

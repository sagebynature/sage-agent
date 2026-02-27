"""Exit codes for Sage CLI — structured codes for CI/scripting."""

from __future__ import annotations

import enum


class SageExitCode(enum.IntEnum):
    """Structured exit codes for ``sage exec`` and CI workflows.

    Values are stable — do not renumber without a deprecation cycle.
    """

    SUCCESS = 0
    """Agent completed successfully."""

    ERROR = 1
    """Generic / unclassified Sage error."""

    CONFIG_ERROR = 2
    """Configuration loading or validation failed."""

    PERMISSION_DENIED = 3
    """Tool execution was denied by permission policy."""

    MAX_TURNS = 4
    """Agent exhausted ``max_turns`` without producing a final response."""

    TIMEOUT = 5
    """Agent or tool execution exceeded the configured timeout."""

    TOOL_ERROR = 6
    """A tool invocation failed."""

    PROVIDER_ERROR = 7
    """The LLM provider call failed."""

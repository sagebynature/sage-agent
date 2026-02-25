"""Custom exceptions for Sage."""


class SageError(Exception):
    """Base exception for all Sage errors."""


class ProviderError(SageError):
    """Raised when an LLM provider call fails."""


class ConfigError(SageError):
    """Raised when configuration loading or validation fails."""


class ToolError(SageError):
    """Raised when tool execution fails."""


class SageMemoryError(SageError):
    """Raised when a memory backend operation fails.

    Named SageMemoryError to avoid shadowing the builtin MemoryError.
    """


class PermissionError(SageError):
    """Raised when tool execution is denied by permission policy.

    Named without 'Sage' prefix for ergonomics — does not shadow
    the builtin PermissionError since that is rarely caught explicitly.
    """

"""Sage — AI agent definition and deployment via configuration.

Agent configs are loaded from ``.md`` files that contain YAML frontmatter and a
markdown body. The frontmatter ``description`` field is display-only, while the
markdown body is used as the system prompt at runtime.
"""

from sage.agent import Agent
from sage.exceptions import (
    SageError,
    SageMemoryError,
    ConfigError,
    ProviderError,
    ToolError,
)
from sage.models import (
    CompletionResult,
    Message,
    StreamChunk,
    ToolCall,
    ToolSchema,
    Usage,
)
from sage.orchestrator import Orchestrator, Pipeline
from sage.providers.litellm_provider import LiteLLMProvider
from sage.tools import ToolBase, ToolRegistry, tool

__all__ = [
    "Agent",
    "SageError",
    "SageMemoryError",
    "CompletionResult",
    "ConfigError",
    "LiteLLMProvider",
    "Message",
    "Orchestrator",
    "Pipeline",
    "ProviderError",
    "StreamChunk",
    "ToolBase",
    "ToolCall",
    "ToolError",
    "ToolRegistry",
    "ToolSchema",
    "Usage",
    "tool",
]

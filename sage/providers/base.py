"""Base provider protocol for LLM providers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from sage.models import CompletionResult, Message, StreamChunk, ToolSchema


@runtime_checkable
class ProviderProtocol(Protocol):
    """Protocol that all LLM providers must implement."""

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: object,
    ) -> CompletionResult:
        """Send a completion request and return the full result."""
        ...

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: object,
    ) -> AsyncIterator[StreamChunk]:
        """Send a streaming completion request and yield chunks.

        When the model response includes tool calls, the final chunk will
        have ``finish_reason="tool_calls"`` and ``StreamChunk.tool_calls``
        populated with the fully-assembled :class:`ToolCall` list.
        """
        ...

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for the given texts.

        Optional capability - implementations may raise NotImplementedError.
        """
        ...

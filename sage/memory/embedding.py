"""Embedding abstractions for the memory system."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import litellm

from sage.providers.base import ProviderProtocol


@runtime_checkable
class EmbeddingProtocol(Protocol):
    """Protocol for embedding providers."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for each text."""
        ...


class ProviderEmbedding:
    """Delegate embedding to an LLM provider's ``embed`` endpoint."""

    def __init__(self, provider: ProviderProtocol) -> None:
        self._provider = provider

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self._provider.embed(texts)


class LiteLLMEmbedding:
    """Embed via litellm.aembedding -- works with any model litellm supports.

    Simpler than ``ProviderEmbedding`` when you just need an embedding model
    string and optional connection kwargs::

        emb = LiteLLMEmbedding("text-embedding-3-large")
        emb = LiteLLMEmbedding("azure/my-deployment", api_base="...", api_key="...")
    """

    def __init__(self, model: str, **kwargs: Any) -> None:
        self._model = model
        self._kwargs = kwargs

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via litellm.aembedding."""
        response = await litellm.aembedding(model=self._model, input=texts, **self._kwargs)
        return [item["embedding"] for item in response.data]

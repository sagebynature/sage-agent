"""Embedding abstractions for the memory system."""

from __future__ import annotations

import logging
import os
from typing import Any, Protocol, runtime_checkable

import httpx
import litellm

from sage.exceptions import ProviderError
from sage.providers.base import ProviderProtocol

logger = logging.getLogger(__name__)

_OLLAMA_TIMEOUT = 60.0


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
        logger.debug("LiteLLMEmbedding initialized with model=%s", model)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via litellm.aembedding."""
        logger.debug("Embedding %d text(s) via model=%s", len(texts), self._model)
        response = await litellm.aembedding(model=self._model, input=texts, **self._kwargs)
        vectors = [item["embedding"] for item in response.data]
        dims = len(vectors[0]) if vectors else 0
        logger.debug("Embedding complete: %d vector(s), dimensions=%d", len(vectors), dims)
        return vectors


class OllamaEmbedding:
    """Embed via Ollama's HTTP API directly (no LiteLLM).

    Reads ``OLLAMA_API_BASE`` from the environment; defaults to
    ``http://localhost:11434``.  The ``base_url`` constructor argument
    takes precedence over the env var::

        emb = OllamaEmbedding("nomic-embed-text")
        emb = OllamaEmbedding("nomic-embed-text", base_url="http://gpu-box:11434")
    """

    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(self, model: str, base_url: str | None = None) -> None:
        self._model = model
        self._base_url = (
            base_url or os.environ.get("OLLAMA_API_BASE") or self.DEFAULT_BASE_URL
        ).rstrip("/")
        logger.debug(
            "OllamaEmbedding initialized: model=%s, base_url=%s",
            self._model,
            self._base_url,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via ``POST /api/embed``."""
        logger.debug("Embedding %d text(s) via Ollama model=%s", len(texts), self._model)
        url = f"{self._base_url}/api/embed"
        try:
            async with httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT) as client:
                response = await client.post(url, json={"model": self._model, "input": texts})
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ProviderError(
                f"Cannot connect to Ollama at {self._base_url}. "
                f"Is Ollama running? Set OLLAMA_API_BASE to override."
            ) from exc
        if response.status_code != 200:
            raise ProviderError(
                f"Ollama /api/embed returned HTTP {response.status_code}: {response.text}"
            )
        try:
            data = response.json()
            return data["embeddings"]
        except (KeyError, ValueError) as exc:
            raise ProviderError(
                f"Ollama /api/embed returned unexpected body: {response.text[:200]}"
            ) from exc


def create_embedding(model_str: str) -> EmbeddingProtocol:
    """Return an :class:`EmbeddingProtocol` for *model_str*.

    Prefix routing:

    * ``"ollama/<model>"``  →  :class:`OllamaEmbedding`
    * anything else         →  :class:`LiteLLMEmbedding`

    Raises :class:`ValueError` if the ``ollama/`` prefix is present but
    no model name follows.
    """
    if model_str.startswith("ollama/"):
        model = model_str[len("ollama/") :]
        if not model:
            raise ValueError("ollama/ prefix requires a model name, e.g. 'ollama/nomic-embed-text'")
        return OllamaEmbedding(model)
    return LiteLLMEmbedding(model_str)

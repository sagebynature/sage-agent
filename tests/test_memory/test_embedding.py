"""Tests for embedding abstractions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sage.memory.embedding import (
    EmbeddingProtocol,
    LiteLLMEmbedding,
    ProviderEmbedding,
)


# ---------------------------------------------------------------------------
# ProviderEmbedding
# ---------------------------------------------------------------------------


class TestProviderEmbedding:
    @pytest.mark.asyncio
    async def test_delegates_to_provider(self) -> None:
        mock_provider = AsyncMock()
        expected = [[0.1, 0.2], [0.3, 0.4]]
        mock_provider.embed.return_value = expected

        emb = ProviderEmbedding(mock_provider)
        result = await emb.embed(["hello", "world"])

        mock_provider.embed.assert_awaited_once_with(["hello", "world"])
        assert result == expected

    @pytest.mark.asyncio
    async def test_satisfies_embedding_protocol(self) -> None:
        mock_provider = AsyncMock()
        emb = ProviderEmbedding(mock_provider)
        assert isinstance(emb, EmbeddingProtocol)


# ---------------------------------------------------------------------------
# LiteLLMEmbedding
# ---------------------------------------------------------------------------


class TestLiteLLMEmbedding:
    @pytest.mark.asyncio
    async def test_calls_litellm_aembedding(self) -> None:
        mock_response = MagicMock()
        mock_response.data = [
            {"embedding": [0.1, 0.2]},
            {"embedding": [0.3, 0.4]},
        ]

        with patch("sage.memory.embedding.litellm") as mock_litellm:
            mock_litellm.aembedding = AsyncMock(return_value=mock_response)
            emb = LiteLLMEmbedding("text-embedding-3-large")
            result = await emb.embed(["hello", "world"])

        mock_litellm.aembedding.assert_awaited_once_with(
            model="text-embedding-3-large", input=["hello", "world"]
        )
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    @pytest.mark.asyncio
    async def test_forwards_kwargs(self) -> None:
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.5]}]

        with patch("sage.memory.embedding.litellm") as mock_litellm:
            mock_litellm.aembedding = AsyncMock(return_value=mock_response)
            emb = LiteLLMEmbedding("my-model", api_base="https://example.com", api_key="k")
            await emb.embed(["test"])

        mock_litellm.aembedding.assert_awaited_once_with(
            model="my-model",
            input=["test"],
            api_base="https://example.com",
            api_key="k",
        )

    def test_satisfies_embedding_protocol(self) -> None:
        emb = LiteLLMEmbedding("any-model")
        assert isinstance(emb, EmbeddingProtocol)

"""Tests for embedding abstractions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from sage.exceptions import ProviderError
from sage.memory.embedding import (
    EmbeddingProtocol,
    LiteLLMEmbedding,
    OllamaEmbedding,
    ProviderEmbedding,
    create_embedding,
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


# ---------------------------------------------------------------------------
# OllamaEmbedding
# ---------------------------------------------------------------------------


class TestOllamaEmbedding:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

        with patch("sage.memory.embedding.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = fake_response

            emb = OllamaEmbedding("nomic-embed-text", base_url="http://localhost:11434")
            result = await emb.embed(["hello", "world"])

        mock_client.post.assert_awaited_once_with(
            "http://localhost:11434/api/embed",
            json={"model": "nomic-embed-text", "input": ["hello", "world"]},
        )
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    @pytest.mark.asyncio
    async def test_connection_error(self) -> None:
        with patch("sage.memory.embedding.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.ConnectError("refused")

            emb = OllamaEmbedding("nomic-embed-text", base_url="http://localhost:11434")
            with pytest.raises(
                ProviderError, match="Cannot connect to Ollama at http://localhost:11434"
            ):
                await emb.embed(["hello"])

    @pytest.mark.asyncio
    async def test_non_200_response(self) -> None:
        fake_response = MagicMock()
        fake_response.status_code = 404
        fake_response.text = "model not found"

        with patch("sage.memory.embedding.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = fake_response

            emb = OllamaEmbedding("nomic-embed-text", base_url="http://localhost:11434")
            with pytest.raises(ProviderError, match="HTTP 404"):
                await emb.embed(["hello"])

    def test_satisfies_embedding_protocol(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OLLAMA_API_BASE", raising=False)
        emb = OllamaEmbedding("nomic-embed-text")
        assert isinstance(emb, EmbeddingProtocol)

    @pytest.mark.asyncio
    async def test_timeout_error(self) -> None:
        with patch("sage.memory.embedding.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.ReadTimeout("timed out")

            emb = OllamaEmbedding("nomic-embed-text", base_url="http://localhost:11434")
            with pytest.raises(ProviderError, match="Cannot connect to Ollama"):
                await emb.embed(["hello"])

    @pytest.mark.asyncio
    async def test_unexpected_response_body(self) -> None:
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"result": "no embeddings key here"}
        fake_response.text = '{"result": "no embeddings key here"}'

        with patch("sage.memory.embedding.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = fake_response

            emb = OllamaEmbedding("nomic-embed-text", base_url="http://localhost:11434")
            with pytest.raises(ProviderError, match="unexpected body"):
                await emb.embed(["hello"])

    @pytest.mark.asyncio
    async def test_read_error(self) -> None:
        with patch("sage.memory.embedding.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.ReadError("connection reset")

            emb = OllamaEmbedding("nomic-embed-text", base_url="http://localhost:11434")
            with pytest.raises(ProviderError, match="Cannot connect to Ollama"):
                await emb.embed(["hello"])

    @pytest.mark.asyncio
    async def test_json_array_response_body(self) -> None:
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = [0.1, 0.2, 0.3]  # array, not object
        fake_response.text = "[0.1, 0.2, 0.3]"

        with patch("sage.memory.embedding.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = fake_response

            emb = OllamaEmbedding("nomic-embed-text", base_url="http://localhost:11434")
            with pytest.raises(ProviderError, match="unexpected body"):
                await emb.embed(["hello"])

    def test_env_var_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_API_BASE", "http://gpu-box:11434")
        emb = OllamaEmbedding("nomic-embed-text")
        assert emb._base_url == "http://gpu-box:11434"

    def test_default_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OLLAMA_API_BASE", raising=False)
        emb = OllamaEmbedding("nomic-embed-text")
        assert emb._base_url == "http://localhost:11434"


# ---------------------------------------------------------------------------
# create_embedding factory
# ---------------------------------------------------------------------------


class TestCreateEmbedding:
    def test_routes_ollama_prefix(self) -> None:
        emb = create_embedding("ollama/nomic-embed-text")
        assert isinstance(emb, OllamaEmbedding)

    def test_routes_plain_model_to_litellm(self) -> None:
        emb = create_embedding("text-embedding-3-large")
        assert isinstance(emb, LiteLLMEmbedding)

    def test_other_prefix_goes_to_litellm(self) -> None:
        # azure/, cohere/, etc. all go to LiteLLM
        emb = create_embedding("azure/my-deployment")
        assert isinstance(emb, LiteLLMEmbedding)

    def test_empty_model_after_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="requires a model name"):
            create_embedding("ollama/")

    def test_whitespace_only_model_after_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="requires a model name"):
            create_embedding("ollama/   ")

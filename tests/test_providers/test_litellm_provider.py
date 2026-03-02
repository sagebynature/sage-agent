"""Tests for the LiteLLM provider implementation."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sage.exceptions import ProviderError
from sage.models import Message, ToolSchema
from sage.providers.litellm_provider import LiteLLMProvider


@pytest.fixture
def provider() -> LiteLLMProvider:
    return LiteLLMProvider("azure/gpt-4o", temperature=0.7)


def _make_response(
    content: str | None = "Hello!",
    tool_calls: list | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    cached_tokens: int = 0,
    cache_creation_tokens: int = 0,
    reasoning_tokens: int = 0,
) -> MagicMock:
    """Build a mock litellm response object."""
    func_mocks = []
    if tool_calls:
        for tc in tool_calls:
            func = SimpleNamespace(name=tc["name"], arguments=tc["arguments"])
            func_mocks.append(SimpleNamespace(id=tc["id"], type="function", function=func))

    message = SimpleNamespace(
        content=content,
        role="assistant",
        tool_calls=func_mocks or None,
    )
    choice = SimpleNamespace(message=message, finish_reason="stop")

    prompt_tokens_details = SimpleNamespace(
        cached_tokens=cached_tokens,
        cache_creation_tokens=cache_creation_tokens,
    )
    completion_tokens_details = SimpleNamespace(
        reasoning_tokens=reasoning_tokens,
    )
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        prompt_tokens_details=prompt_tokens_details,
        completion_tokens_details=completion_tokens_details,
    )
    return MagicMock(choices=[choice], usage=usage)


class TestLiteLLMProviderComplete:
    @patch("sage.providers.litellm_provider.litellm")
    async def test_basic_completion(self, mock_litellm: MagicMock, provider: LiteLLMProvider):
        mock_litellm.acompletion = AsyncMock(return_value=_make_response("Hi there"))
        messages = [Message(role="user", content="Hello")]

        result = await provider.complete(messages)

        assert result.message.role == "assistant"
        assert result.message.content == "Hi there"
        assert result.message.tool_calls is None
        assert result.usage.prompt_tokens == 10
        assert result.usage.completion_tokens == 5
        assert result.usage.total_tokens == 15

    @patch("sage.providers.litellm_provider.litellm")
    async def test_completion_with_tool_calls(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ):
        tool_calls = [{"id": "call_1", "name": "get_weather", "arguments": '{"city": "London"}'}]
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_response(content=None, tool_calls=tool_calls)
        )
        messages = [Message(role="user", content="What's the weather?")]
        tools = [
            ToolSchema(
                name="get_weather",
                description="Get weather",
                parameters={"type": "object", "properties": {"city": {"type": "string"}}},
            )
        ]

        result = await provider.complete(messages, tools=tools)

        assert result.message.tool_calls is not None
        assert len(result.message.tool_calls) == 1
        tc = result.message.tool_calls[0]
        assert tc.id == "call_1"
        assert tc.name == "get_weather"
        assert tc.arguments == {"city": "London"}

    @patch("sage.providers.litellm_provider.litellm")
    async def test_completion_passes_config(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ):
        mock_litellm.acompletion = AsyncMock(return_value=_make_response())
        messages = [Message(role="user", content="Hi")]

        await provider.complete(messages)

        call_kwargs = mock_litellm.acompletion.call_args.kwargs
        assert call_kwargs["model"] == "azure/gpt-4o"
        assert call_kwargs["temperature"] == 0.7

    @patch("sage.providers.litellm_provider.litellm")
    async def test_completion_error_raises_provider_error(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ):
        mock_litellm.acompletion = AsyncMock(side_effect=RuntimeError("API down"))
        messages = [Message(role="user", content="Hello")]

        with pytest.raises(ProviderError, match="LiteLLM completion failed"):
            await provider.complete(messages)


class TestCacheTokenExtraction:
    @patch("sage.providers.litellm_provider.litellm")
    async def test_cache_tokens_extracted(self, mock_litellm: MagicMock, provider: LiteLLMProvider):
        resp = _make_response(
            "Hi", cached_tokens=100, cache_creation_tokens=50, reasoning_tokens=25
        )
        mock_litellm.acompletion = AsyncMock(return_value=resp)
        mock_litellm.completion_cost = MagicMock(return_value=0.005)
        messages = [Message(role="user", content="Hello")]

        result = await provider.complete(messages)

        assert result.usage.cache_read_tokens == 100
        assert result.usage.cache_creation_tokens == 50
        assert result.usage.reasoning_tokens == 25

    @patch("sage.providers.litellm_provider.litellm")
    async def test_cost_calculated_via_litellm(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ):
        resp = _make_response("Hi")
        mock_litellm.acompletion = AsyncMock(return_value=resp)
        mock_litellm.completion_cost = MagicMock(return_value=0.0042)
        messages = [Message(role="user", content="Hello")]

        result = await provider.complete(messages)

        assert result.usage.cost == pytest.approx(0.0042)
        mock_litellm.completion_cost.assert_called_once_with(completion_response=resp)

    @patch("sage.providers.litellm_provider.litellm")
    async def test_cost_fallback_to_zero_on_error(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ):
        resp = _make_response("Hi")
        mock_litellm.acompletion = AsyncMock(return_value=resp)
        mock_litellm.completion_cost = MagicMock(side_effect=Exception("Unknown model"))
        messages = [Message(role="user", content="Hello")]

        result = await provider.complete(messages)

        assert result.usage.cost == 0.0

    @patch("sage.providers.litellm_provider.litellm")
    async def test_missing_token_details_default_to_zero(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ):
        """When prompt_tokens_details / completion_tokens_details are absent, fields default to 0."""
        message = SimpleNamespace(content="Hi", role="assistant", tool_calls=None)
        choice = SimpleNamespace(message=message, finish_reason="stop")
        usage = SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
        resp = MagicMock(choices=[choice], usage=usage)
        mock_litellm.acompletion = AsyncMock(return_value=resp)
        mock_litellm.completion_cost = MagicMock(return_value=0.001)
        messages = [Message(role="user", content="Hello")]

        result = await provider.complete(messages)

        assert result.usage.cache_read_tokens == 0
        assert result.usage.cache_creation_tokens == 0
        assert result.usage.reasoning_tokens == 0
        assert result.usage.cost == pytest.approx(0.001)


class TestLiteLLMProviderStream:
    @patch("sage.providers.litellm_provider.litellm")
    async def test_stream_yields_chunks(self, mock_litellm: MagicMock, provider: LiteLLMProvider):
        async def fake_stream(*args, **kwargs):
            for text in ["Hel", "lo", "!"]:
                delta = SimpleNamespace(content=text)
                choice = SimpleNamespace(delta=delta, finish_reason=None)
                yield MagicMock(choices=[choice])
            delta = SimpleNamespace(content=None)
            choice = SimpleNamespace(delta=delta, finish_reason="stop")
            yield MagicMock(choices=[choice])

        mock_litellm.acompletion = AsyncMock(return_value=fake_stream())
        messages = [Message(role="user", content="Hello")]

        chunks = []
        async for chunk in provider.stream(messages):
            chunks.append(chunk)

        assert len(chunks) == 4
        assert chunks[0].delta == "Hel"
        assert chunks[1].delta == "lo"
        assert chunks[2].delta == "!"
        assert chunks[3].finish_reason == "stop"

    @patch("sage.providers.litellm_provider.litellm")
    async def test_stream_error_raises_provider_error(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ):
        mock_litellm.acompletion = AsyncMock(side_effect=RuntimeError("Stream failed"))
        messages = [Message(role="user", content="Hello")]

        with pytest.raises(ProviderError, match="LiteLLM streaming failed"):
            async for _ in provider.stream(messages):
                pass


class TestLiteLLMProviderEmbed:
    @patch("sage.providers.litellm_provider.litellm")
    async def test_embed_returns_vectors(self, mock_litellm: MagicMock, provider: LiteLLMProvider):
        mock_response = MagicMock()
        mock_response.data = [
            {"embedding": [0.1, 0.2, 0.3]},
            {"embedding": [0.4, 0.5, 0.6]},
        ]
        mock_litellm.aembedding = AsyncMock(return_value=mock_response)

        result = await provider.embed(["hello", "world"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]

    @patch("sage.providers.litellm_provider.litellm")
    async def test_embed_passes_config_kwargs(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ):
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.1]}]
        mock_litellm.aembedding = AsyncMock(return_value=mock_response)

        await provider.embed(["hello"])

        mock_litellm.aembedding.assert_called_once_with(
            model="azure/gpt-4o", input=["hello"], temperature=0.7
        )

    @patch("sage.providers.litellm_provider.litellm")
    async def test_embed_error_raises_provider_error(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ):
        mock_litellm.aembedding = AsyncMock(side_effect=RuntimeError("Embed failed"))

        with pytest.raises(ProviderError, match="LiteLLM embedding failed"):
            await provider.embed(["hello"])


class TestMessageConversion:
    def test_system_message(self, provider: LiteLLMProvider):
        msg = Message(role="system", content="You are helpful")
        d = provider._message_to_dict(msg)
        assert d == {"role": "system", "content": "You are helpful"}

    def test_tool_message(self, provider: LiteLLMProvider):
        msg = Message(role="tool", content="result", tool_call_id="call_1")
        d = provider._message_to_dict(msg)
        assert d == {"role": "tool", "content": "result", "tool_call_id": "call_1"}

    def test_tool_schema_to_dict(self, provider: LiteLLMProvider):
        schema = ToolSchema(
            name="search",
            description="Search the web",
            parameters={"type": "object", "properties": {"q": {"type": "string"}}},
        )
        d = provider._tool_schema_to_dict(schema)
        assert d["type"] == "function"
        assert d["function"]["name"] == "search"
        assert d["function"]["description"] == "Search the web"


class TestLiteLLMProviderLogging:
    @pytest.mark.asyncio
    async def test_complete_logs_request_and_response(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """LiteLLMProvider.complete should log DEBUG for request and response."""
        provider = LiteLLMProvider("gpt-4o")
        mock_response = _make_response(content="Hello")

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            with caplog.at_level(
                logging.DEBUG,
                logger="sage.providers.litellm_provider",
            ):
                await provider.complete([Message(role="user", content="Hello")])

        messages = " ".join(r.message for r in caplog.records)
        assert caplog.records, "Expected at least one log record"
        assert "gpt-4o" in messages or "messages=1" in messages, (
            f"Expected model or message count in logs, got: {messages}"
        )


class TestLiteLLMProviderHelpers:
    """Tests for get_context_window() and count_tokens() helper methods."""

    @patch("sage.providers.litellm_provider.litellm")
    def test_get_context_window_returns_int_on_success(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ) -> None:
        mock_litellm.get_model_info.return_value = {"max_input_tokens": 128_000}
        result = provider.get_context_window()
        assert result == 128_000
        mock_litellm.get_model_info.assert_called_once_with("azure/gpt-4o")

    @patch("sage.providers.litellm_provider.litellm")
    def test_get_context_window_returns_none_on_exception(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ) -> None:
        mock_litellm.get_model_info.side_effect = RuntimeError("Unknown model")
        result = provider.get_context_window()
        assert result is None

    @patch("sage.providers.litellm_provider.litellm")
    def test_get_context_window_returns_none_when_key_missing(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ) -> None:
        mock_litellm.get_model_info.return_value = {}
        result = provider.get_context_window()
        assert result is None

    @patch("sage.providers.litellm_provider.litellm")
    def test_get_context_window_coerces_float_to_int(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ) -> None:
        mock_litellm.get_model_info.return_value = {"max_input_tokens": 32768.0}
        result = provider.get_context_window()
        assert result == 32768
        assert isinstance(result, int)

    @patch("sage.providers.litellm_provider.litellm")
    def test_count_tokens_returns_int_on_success(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ) -> None:
        mock_litellm.token_counter.return_value = 42
        messages: list[dict[str, object]] = [{"role": "user", "content": "Hello"}]
        result = provider.count_tokens(messages)
        assert result == 42
        mock_litellm.token_counter.assert_called_once_with(model="azure/gpt-4o", messages=messages)

    @patch("sage.providers.litellm_provider.litellm")
    def test_count_tokens_returns_zero_on_exception(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ) -> None:
        mock_litellm.token_counter.side_effect = RuntimeError("Counter failed")
        messages: list[dict[str, object]] = [{"role": "user", "content": "Hello"}]
        result = provider.count_tokens(messages)
        assert result == 0

    @patch("sage.providers.litellm_provider.litellm")
    def test_count_tokens_coerces_float_to_int(
        self, mock_litellm: MagicMock, provider: LiteLLMProvider
    ) -> None:
        mock_litellm.token_counter.return_value = 99.7
        messages: list[dict[str, object]] = [{"role": "user", "content": "Hello"}]
        result = provider.count_tokens(messages)
        assert result == 99
        assert isinstance(result, int)


class TestBuildRequestKwargs:
    """Tests for _build_request_kwargs helper."""

    def test_stream_includes_drop_params(self, provider: LiteLLMProvider) -> None:
        """Streaming requests must include drop_params=True for cross-provider compatibility."""
        messages = [Message(role="user", content="Hello")]
        kwargs = provider._build_request_kwargs(messages, stream=True)
        assert kwargs["stream"] is True
        assert kwargs["stream_options"] == {"include_usage": True}
        assert kwargs["drop_params"] is True

    def test_non_stream_omits_drop_params(self, provider: LiteLLMProvider) -> None:
        """Non-streaming requests should not include drop_params."""
        messages = [Message(role="user", content="Hello")]
        kwargs = provider._build_request_kwargs(messages, stream=False)
        assert "stream" not in kwargs
        assert "stream_options" not in kwargs
        assert "drop_params" not in kwargs


class TestModelParamsRetry:
    """Tests for num_retries and retry_after fields on ModelParams."""

    def test_num_retries_in_kwargs(self) -> None:
        """num_retries appears in to_kwargs() output when set."""
        from sage.config import ModelParams

        params = ModelParams(num_retries=3)
        kwargs = params.to_kwargs()
        assert kwargs.get("num_retries") == 3

    def test_retry_after_in_kwargs(self) -> None:
        """retry_after appears in to_kwargs() output when set."""
        from sage.config import ModelParams

        params = ModelParams(retry_after=1.0)
        kwargs = params.to_kwargs()
        assert kwargs.get("retry_after") == 1.0

    def test_none_values_excluded(self) -> None:
        """None retry fields must not appear in kwargs (avoids passing None to litellm)."""
        from sage.config import ModelParams

        params = ModelParams()
        kwargs = params.to_kwargs()
        assert "num_retries" not in kwargs
        assert "retry_after" not in kwargs

    def test_both_retry_params_in_kwargs(self) -> None:
        """Both num_retries and retry_after appear together when both are set."""
        from sage.config import ModelParams

        params = ModelParams(num_retries=5, retry_after=2.5)
        kwargs = params.to_kwargs()
        assert kwargs.get("num_retries") == 5
        assert kwargs.get("retry_after") == 2.5

    @patch("sage.providers.litellm_provider.litellm")
    async def test_retry_params_reach_litellm(self, mock_litellm: MagicMock) -> None:
        """When num_retries is set, it is passed through to litellm.acompletion."""
        mock_litellm.acompletion = AsyncMock(return_value=_make_response())

        provider = LiteLLMProvider("gpt-4o", num_retries=3, retry_after=0.5)
        messages = [Message(role="user", content="Hello")]

        await provider.complete(messages)

        call_kwargs = mock_litellm.acompletion.call_args.kwargs
        assert call_kwargs.get("num_retries") == 3
        assert call_kwargs.get("retry_after") == 0.5

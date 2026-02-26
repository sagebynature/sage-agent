"""LiteLLM-based provider implementation."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import litellm

from sage.exceptions import ProviderError
from sage.models import (
    CompletionResult,
    Message,
    StreamChunk,
    ToolCall,
    ToolSchema,
    Usage,
)

logger = logging.getLogger(__name__)


class LiteLLMProvider:
    """Provider implementation backed by litellm.

    Supports any model string that litellm supports, e.g.:
    - "gpt-4o" (OpenAI)
    - "azure/gpt-4o" (Azure OpenAI)
    - "anthropic/claude-sonnet-4-20250514" (Anthropic)
    - "ollama/llama3" (Ollama)
    """

    def __init__(self, model: str, **kwargs: Any) -> None:
        self.model = model
        self.config = kwargs

    # ── Format conversion helpers ──────────────────────────────────────

    @staticmethod
    def _message_to_dict(msg: Message) -> dict[str, Any]:
        """Convert our Message model to the dict format litellm expects."""
        d: dict[str, Any] = {"role": msg.role}

        if msg.content is not None:
            d["content"] = msg.content

        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in msg.tool_calls
            ]

        if msg.tool_call_id is not None:
            d["tool_call_id"] = msg.tool_call_id

        return d

    @staticmethod
    def _tool_schema_to_dict(tool: ToolSchema) -> dict[str, Any]:
        """Convert our ToolSchema to the litellm/OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    @staticmethod
    def _parse_tool_calls(raw_tool_calls: list[Any] | None) -> list[ToolCall] | None:
        """Convert litellm response tool_calls to our ToolCall model."""
        if not raw_tool_calls:
            return None

        result: list[ToolCall] = []
        for tc in raw_tool_calls:
            func = tc.function if hasattr(tc, "function") else tc.get("function", {})
            name = func.name if hasattr(func, "name") else func.get("name", "")
            raw_args = func.arguments if hasattr(func, "arguments") else func.get("arguments", "{}")

            # arguments may be a JSON string or already a dict
            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args)
                except (json.JSONDecodeError, TypeError):
                    arguments = {}
            else:
                arguments = raw_args if isinstance(raw_args, dict) else {}

            tc_id = tc.id if hasattr(tc, "id") else tc.get("id", "")
            result.append(ToolCall(id=tc_id, name=name, arguments=arguments))

        return result if result else None

    # ── Core provider methods ──────────────────────────────────────────

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """Send a completion request via litellm."""
        logger.debug(
            "Completion request: model=%s, messages=%d, tools=%d",
            self.model,
            len(messages),
            len(tools) if tools else 0,
        )
        request_kwargs = self._build_request_kwargs(messages, tools, **kwargs)

        try:
            response = await litellm.acompletion(**request_kwargs)
        except Exception as exc:
            logger.error("LiteLLM completion failed: %s", exc)
            raise ProviderError(f"LiteLLM completion failed: {exc}") from exc

        choice = response.choices[0]
        resp_message = choice.message

        tool_calls = self._parse_tool_calls(getattr(resp_message, "tool_calls", None))

        message = Message(
            role="assistant",
            content=getattr(resp_message, "content", None),
            tool_calls=tool_calls,
        )

        raw_usage = getattr(response, "usage", None)
        usage = Usage(
            prompt_tokens=getattr(raw_usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(raw_usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(raw_usage, "total_tokens", 0) or 0,
        )

        logger.debug(
            "Completion response: finish_reason=%s, tokens=%d/%d",
            getattr(choice, "finish_reason", "unknown"),
            usage.prompt_tokens,
            usage.completion_tokens,
        )

        return CompletionResult(
            message=message,
            usage=usage,
            raw_response=response,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Send a streaming completion request via litellm.

        Yields ``StreamChunk`` objects as they arrive.  Text content is
        available in ``chunk.delta``.  When the model finishes with tool
        calls (``finish_reason == "tool_calls"``), the final chunk carries
        the fully-assembled ``tool_calls`` list.
        """
        request_kwargs = self._build_request_kwargs(messages, tools, stream=True, **kwargs)

        try:
            response = await litellm.acompletion(**request_kwargs)
        except Exception as exc:
            raise ProviderError(f"LiteLLM streaming failed: {exc}") from exc

        # Accumulators for incremental tool-call deltas.
        # OpenAI/litellm streams tool calls as partial fragments across
        # multiple chunks, keyed by ``index``.  We reassemble them here.
        tc_ids: dict[int, str] = {}  # index -> tool call id
        tc_names: dict[int, str] = {}  # index -> function name
        tc_args: dict[int, str] = {}  # index -> partial JSON arguments

        try:
            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                content = getattr(delta, "content", None) if delta else None
                finish_reason = chunk.choices[0].finish_reason if chunk.choices else None

                # Accumulate incremental tool-call fragments.
                raw_tc_deltas = getattr(delta, "tool_calls", None) if delta else None
                if raw_tc_deltas:
                    for tc_delta in raw_tc_deltas:
                        idx = getattr(tc_delta, "index", 0)
                        tc_id = getattr(tc_delta, "id", None)
                        func = getattr(tc_delta, "function", None)
                        if tc_id:
                            tc_ids[idx] = tc_id
                        if func:
                            name = getattr(func, "name", None)
                            args = getattr(func, "arguments", None)
                            if name:
                                tc_names[idx] = name
                            if args:
                                tc_args[idx] = tc_args.get(idx, "") + args

                # On the final chunk, assemble accumulated tool calls.
                assembled_tool_calls: list[ToolCall] | None = None
                if finish_reason == "tool_calls" and tc_ids:
                    assembled_tool_calls = []
                    for idx in sorted(tc_ids):
                        raw_args = tc_args.get(idx, "{}")
                        try:
                            arguments = json.loads(raw_args)
                        except (json.JSONDecodeError, TypeError):
                            arguments = {}
                        assembled_tool_calls.append(
                            ToolCall(
                                id=tc_ids[idx],
                                name=tc_names.get(idx, ""),
                                arguments=arguments,
                            )
                        )

                # Extract usage from the final chunk when available.
                raw_usage = getattr(chunk, "usage", None)
                chunk_usage: Usage | None = None
                if raw_usage is not None:
                    chunk_usage = Usage(
                        prompt_tokens=getattr(raw_usage, "prompt_tokens", 0) or 0,
                        completion_tokens=getattr(raw_usage, "completion_tokens", 0) or 0,
                        total_tokens=getattr(raw_usage, "total_tokens", 0) or 0,
                    )
                yield StreamChunk(
                    delta=content,
                    finish_reason=finish_reason,
                    tool_calls=assembled_tool_calls,
                    usage=chunk_usage,
                )
        except Exception as exc:
            raise ProviderError(f"LiteLLM stream iteration failed: {exc}") from exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via litellm."""
        try:
            response = await litellm.aembedding(model=self.model, input=texts, **self.config)
        except Exception as exc:
            raise ProviderError(f"LiteLLM embedding failed: {exc}") from exc

        return [item["embedding"] for item in response.data]

    # ── Provider-level model info helpers ─────────────────────────────────

    def get_context_window(self) -> int | None:
        """Return the max input token count for this model, or None if unknown.

        Encapsulates the litellm.get_model_info() call so that callers outside
        ``sage/providers/`` never import litellm directly.
        """
        try:
            model_info = litellm.get_model_info(self.model)
            max_input = model_info.get("max_input_tokens")
            if isinstance(max_input, (int, float)):
                return int(max_input)
        except Exception:
            pass
        return None

    def count_tokens(self, messages: list[dict[str, object]]) -> int:
        """Return an approximate token count for *messages* using litellm.

        Returns 0 on any failure so callers can degrade gracefully.
        """
        try:
            return int(litellm.token_counter(model=self.model, messages=messages))
        except Exception:
            return 0

    # ── Private helpers ────────────────────────────────────────────────

    def _build_request_kwargs(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build the kwargs dict for litellm.acompletion."""
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [self._message_to_dict(m) for m in messages],
            **self.config,
            **kwargs,
        }

        if stream:
            request_kwargs["stream"] = True
            request_kwargs["stream_options"] = {"include_usage": True}
        if tools:
            request_kwargs["tools"] = [self._tool_schema_to_dict(t) for t in tools]

        return request_kwargs

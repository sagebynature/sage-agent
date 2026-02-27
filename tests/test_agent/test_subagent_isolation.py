"""Tests for subagent crash isolation in Agent.delegate()."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from sage.agent import Agent
from sage.models import CompletionResult, Message, StreamChunk, ToolSchema, Usage


# ── Mock Provider ─────────────────────────────────────────────────────


class MockProvider:
    """Minimal mock provider that returns predetermined CompletionResult responses."""

    def __init__(self, responses: list[CompletionResult]) -> None:
        self.responses = list(responses)
        self.call_count = 0

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: Any,
    ) -> CompletionResult:
        result = self.responses[self.call_count]
        self.call_count += 1
        return result

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        result = self.responses[self.call_count]
        self.call_count += 1
        if result.message.content:
            for char in result.message.content:
                yield StreamChunk(delta=char)
        yield StreamChunk(finish_reason="stop")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


def _text_result(content: str) -> CompletionResult:
    """Create a CompletionResult with a plain text assistant message."""
    return CompletionResult(
        message=Message(role="assistant", content=content),
        usage=Usage(),
    )


def _make_parent_agent(subagents: dict[str, Agent] | None = None) -> Agent:
    """Create a parent agent with a mock provider."""
    provider = MockProvider([_text_result("done")])
    return Agent(
        name="parent",
        model="test-model",
        provider=provider,
        subagents=subagents or {},
    )


def _make_subagent(name: str = "sub") -> Agent:
    """Create a subagent with a mock provider."""
    provider = MockProvider([_text_result("subagent result")])
    return Agent(
        name=name,
        model="test-model",
        provider=provider,
    )


# ── Tests ─────────────────────────────────────────────────────────────


class TestSubagentIsolation:
    """Tests for crash isolation in Agent.delegate()."""

    @pytest.mark.asyncio
    async def test_subagent_exception_returns_error_string(self) -> None:
        """When subagent.run raises RuntimeError, delegate() returns error string with [Subagent Error]."""
        subagent = _make_subagent("worker")
        parent = _make_parent_agent(subagents={"worker": subagent})

        with patch.object(subagent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError("something went wrong")
            result = await parent.delegate("worker", "do some task")

        assert "[Subagent Error]" in result

    @pytest.mark.asyncio
    async def test_subagent_error_contains_exception_type(self) -> None:
        """Error string contains the exception class name."""
        subagent = _make_subagent("worker")
        parent = _make_parent_agent(subagents={"worker": subagent})

        with patch.object(subagent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ValueError("bad input")
            result = await parent.delegate("worker", "do some task")

        assert "ValueError" in result

    @pytest.mark.asyncio
    async def test_subagent_error_contains_agent_name(self) -> None:
        """Error string contains the subagent's name."""
        subagent = _make_subagent("my-worker")
        parent = _make_parent_agent(subagents={"my-worker": subagent})

        with patch.object(subagent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError("crash")
            result = await parent.delegate("my-worker", "do some task")

        assert "my-worker" in result

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_propagates(self) -> None:
        """When subagent.run raises KeyboardInterrupt, delegate() re-raises it."""
        subagent = _make_subagent("worker")
        parent = _make_parent_agent(subagents={"worker": subagent})

        with patch.object(subagent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = KeyboardInterrupt()
            with pytest.raises(KeyboardInterrupt):
                await parent.delegate("worker", "do some task")

    @pytest.mark.asyncio
    async def test_successful_subagent_not_affected(self) -> None:
        """When subagent.run succeeds, result is returned normally."""
        subagent = _make_subagent("worker")
        parent = _make_parent_agent(subagents={"worker": subagent})

        with patch.object(subagent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "success result"
            result = await parent.delegate("worker", "do some task")

        assert result == "success result"

"""Tests for Pipeline — sequential agent execution."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from sage.agent import Agent
from sage.models import (
    CompletionResult,
    Message,
    StreamChunk,
    ToolSchema,
    Usage,
)
from sage.orchestrator.pipeline import Pipeline


# ── Mock Provider ─────────────────────────────────────────────────────


class MockProvider:
    """Mock provider that returns predetermined CompletionResult responses."""

    def __init__(self, responses: list[CompletionResult]) -> None:
        self.responses = list(responses)
        self.call_count = 0
        self.call_args: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: Any,
    ) -> CompletionResult:
        self.call_args.append({"messages": list(messages), "tools": tools})
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


# ── Helpers ────────────────────────────────────────────────────────────


def _text_result(content: str) -> CompletionResult:
    return CompletionResult(
        message=Message(role="assistant", content=content),
        usage=Usage(),
    )


def _make_agent(name: str, response: str) -> Agent:
    """Create an agent with a MockProvider returning a single text response."""
    return Agent(
        name=name,
        model="test-model",
        provider=MockProvider([_text_result(response)]),
    )


# ── Tests: Pipeline ───────────────────────────────────────────────────


class TestPipeline:
    """Tests for Pipeline sequential execution."""

    @pytest.mark.asyncio
    async def test_sequential_pipeline(self) -> None:
        """Output chains through 3 agents sequentially."""
        agent1 = _make_agent("step1", "step1-output")
        agent2 = _make_agent("step2", "step2-output")
        agent3 = _make_agent("step3", "final-output")

        pipeline = Pipeline([agent1, agent2, agent3])
        result = await pipeline.run("initial input")

        assert result == "final-output"

        # Verify each agent received the previous agent's output.
        p1: MockProvider = agent1.provider  # type: ignore[assignment]
        p2: MockProvider = agent2.provider  # type: ignore[assignment]
        p3: MockProvider = agent3.provider  # type: ignore[assignment]

        assert p1.call_args[0]["messages"][-1].content == "initial input"
        assert p2.call_args[0]["messages"][-1].content == "step1-output"
        assert p3.call_args[0]["messages"][-1].content == "step2-output"


# ── Tests: >> operator ────────────────────────────────────────────────


class TestRshiftOperator:
    """Tests for the >> pipeline operator."""

    def test_rshift_operator(self) -> None:
        """agent1 >> agent2 creates a Pipeline with both agents."""
        agent1 = _make_agent("a1", "out1")
        agent2 = _make_agent("a2", "out2")

        pipeline = agent1 >> agent2

        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.agents) == 2
        assert pipeline.agents[0].name == "a1"
        assert pipeline.agents[1].name == "a2"

    def test_rshift_chain(self) -> None:
        """agent1 >> agent2 >> agent3 creates a Pipeline with 3 agents."""
        agent1 = _make_agent("a1", "out1")
        agent2 = _make_agent("a2", "out2")
        agent3 = _make_agent("a3", "out3")

        pipeline = agent1 >> agent2 >> agent3

        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.agents) == 3
        assert [a.name for a in pipeline.agents] == ["a1", "a2", "a3"]

    def test_pipeline_rshift_agent(self) -> None:
        """Pipeline >> agent appends the agent to the pipeline."""
        agent1 = _make_agent("a1", "out1")
        agent2 = _make_agent("a2", "out2")
        agent3 = _make_agent("a3", "out3")

        pipeline = Pipeline([agent1, agent2])
        extended = pipeline >> agent3

        assert isinstance(extended, Pipeline)
        assert len(extended.agents) == 3
        assert [a.name for a in extended.agents] == ["a1", "a2", "a3"]

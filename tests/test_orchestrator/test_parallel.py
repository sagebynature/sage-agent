"""Tests for Orchestrator — parallel and race execution of agents."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import pytest

from sage.agent import Agent
from sage.exceptions import SageError
from sage.models import (
    CompletionResult,
    Message,
    StreamChunk,
    ToolSchema,
    Usage,
)
from sage.orchestrator.parallel import Orchestrator


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


class FailingProvider:
    """Provider that always raises an exception."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: Any,
    ) -> CompletionResult:
        raise self.error

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        raise self.error
        yield  # Make it a generator  # pragma: no cover

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


def _make_failing_agent(name: str, error: Exception) -> Agent:
    """Create an agent whose provider always raises."""
    return Agent(
        name=name,
        model="test-model",
        provider=FailingProvider(error),
    )


# ── Tests: run_parallel ───────────────────────────────────────────────


class TestRunParallel:
    """Tests for Orchestrator.run_parallel."""

    @pytest.mark.asyncio
    async def test_run_parallel_same_input(self) -> None:
        """Three agents receive the same input and all succeed."""
        agents = [
            _make_agent("alpha", "Alpha response"),
            _make_agent("beta", "Beta response"),
            _make_agent("gamma", "Gamma response"),
        ]

        results = await Orchestrator.run_parallel(agents, "shared input")

        assert len(results) == 3
        assert all(r.success for r in results)
        assert results[0].agent_name == "alpha"
        assert results[0].output == "Alpha response"
        assert results[1].agent_name == "beta"
        assert results[1].output == "Beta response"
        assert results[2].agent_name == "gamma"
        assert results[2].output == "Gamma response"

    @pytest.mark.asyncio
    async def test_run_parallel_different_inputs(self) -> None:
        """Each agent gets a different input."""
        agents = [
            _make_agent("a1", "Response 1"),
            _make_agent("a2", "Response 2"),
        ]

        results = await Orchestrator.run_parallel(agents, ["input one", "input two"])

        assert len(results) == 2
        assert results[0].output == "Response 1"
        assert results[1].output == "Response 2"

        # Verify each agent received its own input.
        p0: MockProvider = agents[0].provider  # type: ignore[assignment]
        p1: MockProvider = agents[1].provider  # type: ignore[assignment]
        assert p0.call_args[0]["messages"][-1].content == "input one"
        assert p1.call_args[0]["messages"][-1].content == "input two"

    @pytest.mark.asyncio
    async def test_run_parallel_mismatched_lengths_raises(self) -> None:
        """Input list length != agent count raises SageError."""
        agents = [_make_agent("a", "ok"), _make_agent("b", "ok")]

        with pytest.raises(SageError, match="Number of inputs"):
            await Orchestrator.run_parallel(agents, ["only one"])

    @pytest.mark.asyncio
    async def test_run_parallel_partial_failure(self) -> None:
        """One agent fails, others succeed — all results collected."""
        agents = [
            _make_agent("good1", "Success 1"),
            _make_failing_agent("bad", RuntimeError("boom")),
            _make_agent("good2", "Success 2"),
        ]

        results = await Orchestrator.run_parallel(agents, "test input")

        assert len(results) == 3

        assert results[0].success is True
        assert results[0].output == "Success 1"

        assert results[1].success is False
        assert results[1].agent_name == "bad"
        assert isinstance(results[1].error, RuntimeError)
        assert results[1].output == ""

        assert results[2].success is True
        assert results[2].output == "Success 2"


# ── Tests: run_race ───────────────────────────────────────────────────


class TestRunRace:
    """Tests for Orchestrator.run_race."""

    @pytest.mark.asyncio
    async def test_run_race_first_wins(self) -> None:
        """The first agent to complete successfully wins."""
        agents = [
            _make_agent("fast", "I won"),
            _make_agent("slow", "Too late"),
        ]

        result = await Orchestrator.run_race(agents, "go")

        assert result.success is True
        # At least one agent should have produced a result.
        assert result.output in ("I won", "Too late")
        assert result.agent_name in ("fast", "slow")

    @pytest.mark.asyncio
    async def test_run_race_all_fail(self) -> None:
        """All agents fail — raises SageError with collected errors."""
        agents = [
            _make_failing_agent("f1", RuntimeError("err1")),
            _make_failing_agent("f2", ValueError("err2")),
        ]

        with pytest.raises(SageError, match="All agents failed"):
            await Orchestrator.run_race(agents, "go")

    @pytest.mark.asyncio
    async def test_race_cancelled_tasks_are_awaited(self) -> None:
        """Losing tasks have their cancellation properly awaited (finally blocks run)."""
        import asyncio

        finally_ran: list[str] = []

        async def _fast_run(_input: str) -> str:
            return "winner"

        async def _slow_run(name: str, _input: str) -> str:
            try:
                await asyncio.sleep(10)
                return "should never get here"
            finally:
                finally_ran.append(name)

        class _DirectProvider:
            """Provider whose complete() delegates to a supplied coroutine factory."""

            def __init__(self, coro_factory: Any) -> None:
                self._factory = coro_factory

            async def complete(
                self,
                messages: list[Message],
                tools: list[ToolSchema] | None = None,
                **kwargs: Any,
            ) -> CompletionResult:
                content = await self._factory(messages[-1].content if messages else "")
                return CompletionResult(
                    message=Message(role="assistant", content=content),
                    usage=Usage(),
                )

            async def stream(
                self,
                messages: list[Message],
                tools: list[ToolSchema] | None = None,
                **kwargs: Any,
            ) -> AsyncIterator[StreamChunk]:
                raise NotImplementedError  # pragma: no cover
                yield  # make it a generator  # pragma: no cover

            async def embed(self, texts: list[str]) -> list[list[float]]:
                raise NotImplementedError  # pragma: no cover

        winner_agent = Agent(
            name="winner",
            model="test-model",
            provider=_DirectProvider(_fast_run),
        )
        loser1_agent = Agent(
            name="loser1",
            model="test-model",
            provider=_DirectProvider(lambda inp: _slow_run("loser1", inp)),
        )
        loser2_agent = Agent(
            name="loser2",
            model="test-model",
            provider=_DirectProvider(lambda inp: _slow_run("loser2", inp)),
        )

        result = await Orchestrator.run_race([winner_agent, loser1_agent, loser2_agent], "go")

        assert result.success is True
        assert result.output == "winner"
        # Both losing tasks must have had their finally blocks executed,
        # proving that cancellation was awaited rather than fire-and-forget.
        assert "loser1" in finally_ran, "loser1 finally block did not run"
        assert "loser2" in finally_ran, "loser2 finally block did not run"


class TestOrchestratorLogging:
    @pytest.mark.asyncio
    async def test_run_parallel_logs_start_and_results(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Orchestrator.run_parallel should log INFO with agent count."""
        agents = [_make_agent("agent-a", "done"), _make_agent("agent-b", "done")]

        with caplog.at_level(logging.INFO, logger="sage.orchestrator.parallel"):
            await Orchestrator.run_parallel(agents, "test input")

        all_messages = " ".join(r.message for r in caplog.records)
        assert "2" in all_messages, f"Expected agent count in logs, got: {all_messages}"

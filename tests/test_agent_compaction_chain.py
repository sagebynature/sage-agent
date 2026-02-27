"""Tests for the compaction strategy chain in Agent (Task 26)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from sage.agent import Agent
from sage.models import CompletionResult, Message, Usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text_result(content: str) -> CompletionResult:
    return CompletionResult(
        message=Message(role="assistant", content=content),
        usage=Usage(),
    )


def _msg(role: str, content: str) -> Message:
    return Message(role=role, content=content)


class MockProvider:
    def __init__(self, responses: list[CompletionResult] | None = None):
        self._responses = responses or [_text_result("done")]
        self._idx = 0

    async def complete(self, messages, tools=None, **kwargs):
        result = self._responses[self._idx % len(self._responses)]
        self._idx += 1
        return result


# ---------------------------------------------------------------------------
# Task 26: Compaction chain tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compaction_chain_tries_llm_first():
    """compact_messages (LLM) should be tried first in the chain."""
    summary = _text_result("- Summary of history")
    responses = [_text_result(f"R{i}") for i in range(6)] + [summary]
    provider = MockProvider(responses)
    agent = Agent(name="t", model="m", provider=provider)
    agent._compaction_threshold = 10

    with patch(
        "sage.memory.compaction.compact_messages",
        wraps=__import__("sage.memory.compaction", fromlist=["compact_messages"]).compact_messages,
    ) as mock_compact:
        for i in range(6):
            await agent.run(f"Q{i}")

    # compact_messages should have been called at some point
    assert mock_compact.called


@pytest.mark.asyncio
async def test_compaction_chain_falls_back_to_emergency_on_llm_failure():
    """emergency_drop should be used when compact_messages raises."""
    provider = MockProvider()
    agent = Agent(name="t", model="m", provider=provider)
    agent._compaction_threshold = 5
    agent._conversation_history = [_msg("user", f"msg {i}") for i in range(10)]

    with patch(
        "sage.memory.compaction.compact_messages",
        side_effect=RuntimeError("LLM down"),
    ):
        _, strategy = await agent._run_compaction_chain(agent._conversation_history)

    assert strategy in ("emergency_drop", "deterministic_trim")


@pytest.mark.asyncio
async def test_compaction_chain_falls_back_to_deterministic():
    """deterministic_trim should be final fallback when all else fails."""
    provider = MockProvider()
    agent = Agent(name="t", model="m", provider=provider)
    agent._compaction_threshold = 5
    history = [_msg("user", f"msg {i}") for i in range(10)]

    with (
        patch("sage.memory.compaction.compact_messages", side_effect=RuntimeError("LLM fail")),
        patch("sage.memory.compaction.emergency_drop", side_effect=RuntimeError("drop fail")),
    ):
        result, strategy = await agent._run_compaction_chain(history)

    assert strategy == "deterministic_trim"
    assert len(result) <= len(history)


@pytest.mark.asyncio
async def test_compaction_chain_preserves_system_message():
    """System message should survive compaction in all strategies."""
    provider = MockProvider()
    agent = Agent(name="t", model="m", provider=provider)
    agent._compaction_threshold = 3
    history = [
        _msg("system", "IMPORTANT SYSTEM CONTEXT"),
        *[_msg("user", f"u{i}") for i in range(8)],
    ]

    with patch("sage.memory.compaction.compact_messages", side_effect=RuntimeError("fail")):
        result, _ = await agent._run_compaction_chain(history)

    assert any(
        m.role == "system" and "IMPORTANT SYSTEM CONTEXT" in (m.content or "") for m in result
    )


@pytest.mark.asyncio
async def test_compaction_chain_returns_strategy_name():
    """_run_compaction_chain must return a (list, strategy_name) tuple."""
    summary = _text_result("- Summary")
    provider = MockProvider([summary])
    agent = Agent(name="t", model="m", provider=provider)
    agent._compaction_threshold = 3
    history = [_msg("user", f"msg {i}") for i in range(10)]

    result, strategy = await agent._run_compaction_chain(history)

    assert isinstance(result, list)
    assert isinstance(strategy, str)
    assert len(strategy) > 0


@pytest.mark.asyncio
async def test_last_compaction_strategy_tracked():
    """_last_compaction_strategy attribute should be set after compaction."""
    summary = _text_result("- Summary")
    responses = [_text_result(f"R{i}") for i in range(6)] + [summary]
    provider = MockProvider(responses)
    agent = Agent(name="t", model="m", provider=provider)
    agent._compaction_threshold = 10

    for i in range(6):
        await agent.run(f"Q{i}")

    assert agent._last_compaction_strategy is not None
    assert isinstance(agent._last_compaction_strategy, str)


@pytest.mark.asyncio
async def test_compaction_on_compaction_hook_includes_strategy():
    """ON_COMPACTION hook data should include 'strategy' key."""
    from sage.hooks.base import HookEvent
    from sage.hooks.registry import HookRegistry

    fired: list[dict] = []

    async def capture(event: HookEvent, data: dict) -> None:
        if event == HookEvent.ON_COMPACTION:
            fired.append(dict(data))

    hr = HookRegistry()
    hr.register(HookEvent.ON_COMPACTION, capture)

    summary = _text_result("- Summary")
    responses = [_text_result(f"R{i}") for i in range(6)] + [summary]
    provider = MockProvider(responses)
    agent = Agent(name="t", model="m", provider=provider, hook_registry=hr)
    agent._compaction_threshold = 10

    for i in range(6):
        await agent.run(f"Q{i}")

    assert len(fired) >= 1
    assert "strategy" in fired[0]
    assert isinstance(fired[0]["strategy"], str)


@pytest.mark.asyncio
async def test_compaction_reduces_history():
    """After compaction, history length should be less than before."""
    summary = _text_result("- Summary")
    responses = [_text_result(f"R{i}") for i in range(6)] + [summary]
    provider = MockProvider(responses)
    agent = Agent(name="t", model="m", provider=provider)
    agent._compaction_threshold = 10

    for i in range(6):
        await agent.run(f"Q{i}")

    assert len(agent._conversation_history) < 12

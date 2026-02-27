"""Tests for hook emission points in Agent run/stream/delegate/compact loops (Task 25)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from sage.agent import Agent
from sage.hooks.base import HookEvent
from sage.hooks.registry import HookRegistry
from sage.models import CompletionResult, Message, Usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text_result(content: str) -> CompletionResult:
    return CompletionResult(
        message=Message(role="assistant", content=content),
        usage=Usage(),
    )


class MockProvider:
    def __init__(self, responses: list[CompletionResult]):
        self._responses = list(responses)
        self._idx = 0

    async def complete(self, messages, tools=None, **kwargs):
        result = self._responses[self._idx % len(self._responses)]
        self._idx += 1
        return result


# ---------------------------------------------------------------------------
# T25: Hook emission tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pre_llm_call_hook_fires():
    """PRE_LLM_CALL hook should receive model, messages, and tool_schemas."""
    fired: list[dict] = []

    async def capture(event: HookEvent, data: dict) -> None:
        if event == HookEvent.PRE_LLM_CALL:
            fired.append(dict(data))

    hr = HookRegistry()
    hr.register(HookEvent.PRE_LLM_CALL, capture)

    provider = MockProvider([_text_result("hello")])
    agent = Agent(name="t", model="m", provider=provider, hook_registry=hr)
    await agent.run("test")

    assert len(fired) >= 1
    assert "model" in fired[0]
    assert "messages" in fired[0]
    assert "tool_schemas" in fired[0]
    assert fired[0]["model"] == "m"


@pytest.mark.asyncio
async def test_post_llm_call_hook_fires():
    """POST_LLM_CALL hook should fire after provider.complete()."""
    fired: list[HookEvent] = []

    async def capture(event: HookEvent, data: dict) -> None:
        fired.append(event)

    hr = HookRegistry()
    hr.register(HookEvent.POST_LLM_CALL, capture)

    provider = MockProvider([_text_result("response")])
    agent = Agent(name="t", model="m", provider=provider, hook_registry=hr)
    await agent.run("test")

    assert HookEvent.POST_LLM_CALL in fired


@pytest.mark.asyncio
async def test_post_tool_execute_hook_fires():
    """POST_TOOL_EXECUTE hook should fire after each tool call with name, args, result."""
    from sage.tools.decorator import tool

    @tool
    def echo_tool(message: str) -> str:
        """Echo."""
        return message

    fired: list[dict] = []

    async def capture(event: HookEvent, data: dict) -> None:
        if event == HookEvent.POST_TOOL_EXECUTE:
            fired.append(dict(data))

    hr = HookRegistry()
    hr.register(HookEvent.POST_TOOL_EXECUTE, capture)

    from sage.models import ToolCall

    tool_call_result = CompletionResult(
        message=Message(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id="c1", name="echo_tool", arguments={"message": "hi"})],
        ),
        usage=Usage(),
    )
    final_result = _text_result("done")

    provider = MockProvider([tool_call_result, final_result])
    agent = Agent(name="t", model="m", provider=provider, hook_registry=hr, tools=[echo_tool])
    await agent.run("test")

    assert len(fired) == 1
    assert fired[0]["tool_name"] == "echo_tool"
    assert "arguments" in fired[0]
    assert "result" in fired[0]
    assert "hi" in fired[0]["result"]


@pytest.mark.asyncio
async def test_on_delegation_hook_fires():
    """ON_DELEGATION hook should fire before subagent.run() with target and input."""
    fired: list[dict] = []

    async def capture(event: HookEvent, data: dict) -> None:
        if event == HookEvent.ON_DELEGATION:
            fired.append(dict(data))

    hr = HookRegistry()
    hr.register(HookEvent.ON_DELEGATION, capture)

    # Create a parent agent with a mock subagent
    mock_subagent = AsyncMock(spec=Agent)
    mock_subagent.name = "worker"
    mock_subagent.run = AsyncMock(return_value="subresult")

    provider = MockProvider([_text_result("delegated")])
    parent = Agent(name="parent", model="m", provider=provider, hook_registry=hr)
    parent.subagents["worker"] = mock_subagent

    await parent.delegate("worker", "do the thing")

    assert len(fired) == 1
    assert fired[0]["target"] == "worker"
    assert fired[0]["input"] == "do the thing"


@pytest.mark.asyncio
async def test_on_compaction_hook_fires():
    """ON_COMPACTION hook should fire after successful history compaction."""
    fired: list[dict] = []

    async def capture(event: HookEvent, data: dict) -> None:
        if event == HookEvent.ON_COMPACTION:
            fired.append(dict(data))

    hr = HookRegistry()
    hr.register(HookEvent.ON_COMPACTION, capture)

    # Build compact_messages response (the summary)
    summary = _text_result("- Summary of conversation")
    responses = [_text_result(f"R{i}") for i in range(6)] + [summary]
    provider = MockProvider(responses)
    agent = Agent(name="t", model="m", provider=provider, hook_registry=hr)
    agent._compaction_threshold = 10

    for i in range(6):
        await agent.run(f"Q{i}")

    assert len(fired) >= 1
    assert "before_count" in fired[0]
    assert "after_count" in fired[0]
    assert fired[0]["before_count"] > fired[0]["after_count"]


@pytest.mark.asyncio
async def test_no_hooks_no_change():
    """Agent with no hooks registered should behave identically."""
    provider = MockProvider([_text_result("response")])
    agent = Agent(name="t", model="m", provider=provider)  # no hook_registry
    result = await agent.run("test")
    assert result == "response"


@pytest.mark.asyncio
async def test_hook_error_is_caught():
    """Hook that raises should not crash the agent."""

    async def bad_hook(event: HookEvent, data: dict) -> None:
        raise RuntimeError("boom")

    hr = HookRegistry()
    hr.register(HookEvent.PRE_LLM_CALL, bad_hook)

    provider = MockProvider([_text_result("still works")])
    agent = Agent(name="t", model="m", provider=provider, hook_registry=hr)
    result = await agent.run("test")
    assert result == "still works"


def test_agent_has_hook_registry_attribute():
    """Agent should always have _hook_registry attribute after init."""
    provider = AsyncMock()
    provider.complete = AsyncMock(return_value=_text_result("ok"))
    agent = Agent(name="t", model="m", provider=provider)
    assert hasattr(agent, "_hook_registry")
    assert isinstance(agent._hook_registry, HookRegistry)


def test_hook_registry_passed_to_init():
    """Custom HookRegistry passed to init should be stored on agent."""
    hr = HookRegistry()
    provider = AsyncMock()
    agent = Agent(name="t", model="m", provider=provider, hook_registry=hr)
    assert agent._hook_registry is hr


@pytest.mark.asyncio
async def test_hooks_fire_in_correct_order():
    """PRE_LLM_CALL should fire before POST_LLM_CALL."""
    order: list[str] = []

    async def pre(event: HookEvent, data: dict) -> None:
        if event == HookEvent.PRE_LLM_CALL:
            order.append("pre")

    async def post(event: HookEvent, data: dict) -> None:
        if event == HookEvent.POST_LLM_CALL:
            order.append("post")

    hr = HookRegistry()
    hr.register(HookEvent.PRE_LLM_CALL, pre)
    hr.register(HookEvent.POST_LLM_CALL, post)

    provider = MockProvider([_text_result("done")])
    agent = Agent(name="t", model="m", provider=provider, hook_registry=hr)
    await agent.run("test")

    assert order == ["pre", "post"]

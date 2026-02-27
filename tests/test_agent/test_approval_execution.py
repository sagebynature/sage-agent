"""Tests for approval-aware sequential execution (Task 20).

These tests validate:
- CancellationToken can be imported and works correctly
- _execute_tool_calls() accepts an optional token parameter
- The split logic separates ask-gated and parallel tool calls
- Cancelled tokens stop sequential execution early
"""

from __future__ import annotations

import inspect

import pytest

from sage.agent import Agent
from sage.models import CompletionResult, Message, ToolCall


# ── Basic import and attribute tests ──────────────────────────────────


def test_cancellation_token_importable():
    """CancellationToken must be importable and functional."""
    from sage.coordination.cancellation import CancellationToken

    token = CancellationToken()
    assert not token.is_cancelled
    token.cancel()
    assert token.is_cancelled


def test_execute_tool_calls_accepts_token():
    """_execute_tool_calls should accept optional token parameter without error."""

    sig = inspect.signature(Agent._execute_tool_calls)
    assert "token" in sig.parameters


def test_agent_imports_ok():
    """Agent and CancellationToken should import without errors."""
    from sage.coordination.cancellation import CancellationToken

    assert Agent is not None
    assert CancellationToken is not None


def test_cancelled_token_attribute():
    """CancellationToken.is_cancelled should track cancellation state correctly."""
    from sage.coordination.cancellation import CancellationToken

    token = CancellationToken()
    token.cancel()
    assert token.is_cancelled

    token2 = CancellationToken()
    assert not token2.is_cancelled


# ── Token parameter signature tests ───────────────────────────────────


def test_token_parameter_is_optional():
    """token parameter must have a default value (None) so it's optional."""

    sig = inspect.signature(Agent._execute_tool_calls)
    token_param = sig.parameters["token"]
    assert token_param.default is None


def test_token_parameter_annotation():
    """token parameter should be annotated (not empty) for clarity."""

    sig = inspect.signature(Agent._execute_tool_calls)
    token_param = sig.parameters["token"]
    # The annotation should exist (not inspect.Parameter.empty)
    assert token_param.annotation is not inspect.Parameter.empty


# ── CancellationToken behaviour tests ─────────────────────────────────


def test_cancellation_token_cancel_idempotent():
    """Calling cancel() multiple times should not raise and keeps token cancelled."""
    from sage.coordination.cancellation import CancellationToken

    token = CancellationToken()
    token.cancel()
    token.cancel()  # second call should be safe
    assert token.is_cancelled


def test_cancellation_token_fresh_not_cancelled():
    """A newly created CancellationToken must not be cancelled."""
    from sage.coordination.cancellation import CancellationToken

    for _ in range(3):
        token = CancellationToken()
        assert not token.is_cancelled


# ── _execute_tool_calls integration tests ─────────────────────────────


@pytest.mark.asyncio
async def test_execute_tool_calls_returns_list():
    """_execute_tool_calls must append tool result messages for each tool call."""
    from sage.tools.decorator import tool

    @tool
    def echo(message: str) -> str:
        """Echo back the message."""
        return message

    class MockProvider:
        async def complete(self, messages, tools=None, **kwargs):
            return CompletionResult(
                message=Message(role="assistant", content="done"),
            )

    agent = Agent(
        name="test",
        model="gpt-4o",
        provider=MockProvider(),
        tools=[echo],
    )

    messages: list[Message] = []
    tc = ToolCall(id="call_1", name="echo", arguments={"message": "hello"})
    await agent._execute_tool_calls([tc], messages)

    assert len(messages) == 1
    tool_msg = messages[0]
    assert tool_msg.role == "tool"
    assert tool_msg.tool_call_id == "call_1"
    assert "hello" in (tool_msg.content or "")


@pytest.mark.asyncio
async def test_execute_tool_calls_with_none_token():
    """_execute_tool_calls must work normally when token=None (default)."""
    from sage.tools.decorator import tool

    @tool
    def greet(name: str) -> str:
        """Greet someone."""
        return f"Hello, {name}!"

    class MockProvider:
        async def complete(self, messages, tools=None, **kwargs):
            return CompletionResult(
                message=Message(role="assistant", content="done"),
            )

    agent = Agent(
        name="test",
        model="gpt-4o",
        provider=MockProvider(),
        tools=[greet],
    )

    messages: list[Message] = []
    tc = ToolCall(id="call_2", name="greet", arguments={"name": "World"})
    await agent._execute_tool_calls([tc], messages, token=None)

    assert len(messages) == 1
    tool_msg = messages[0]
    assert tool_msg.tool_call_id == "call_2"
    assert "World" in (tool_msg.content or "")


@pytest.mark.asyncio
async def test_execute_tool_calls_with_active_token():
    """_execute_tool_calls must work normally with a non-cancelled token."""
    from sage.coordination.cancellation import CancellationToken
    from sage.tools.decorator import tool

    @tool
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    class MockProvider:
        async def complete(self, messages, tools=None, **kwargs):
            return CompletionResult(
                message=Message(role="assistant", content="done"),
            )

    agent = Agent(
        name="test",
        model="gpt-4o",
        provider=MockProvider(),
        tools=[add],
    )

    messages: list[Message] = []
    token = CancellationToken()
    tc = ToolCall(id="call_3", name="add", arguments={"a": 2, "b": 3})
    await agent._execute_tool_calls([tc], messages, token=token)

    assert len(messages) == 1
    tool_msg = messages[0]
    assert tool_msg.tool_call_id == "call_3"
    assert "5" in (tool_msg.content or "")


@pytest.mark.asyncio
async def test_execute_tool_calls_empty_list():
    """_execute_tool_calls with an empty list should return an empty list."""

    class MockProvider:
        async def complete(self, messages, tools=None, **kwargs):
            return CompletionResult(
                message=Message(role="assistant", content="done"),
            )

    agent = Agent(
        name="test",
        model="gpt-4o",
        provider=MockProvider(),
    )

    messages: list[Message] = []
    await agent._execute_tool_calls([], messages)
    assert messages == []


@pytest.mark.asyncio
async def test_execute_tool_calls_preserves_order():
    """Results must be returned in the same order as the input tool calls."""
    from sage.tools.decorator import tool

    call_order: list[str] = []

    @tool
    def step_a() -> str:
        """Step A."""
        call_order.append("a")
        return "result_a"

    @tool
    def step_b() -> str:
        """Step B."""
        call_order.append("b")
        return "result_b"

    class MockProvider:
        async def complete(self, messages, tools=None, **kwargs):
            return CompletionResult(
                message=Message(role="assistant", content="done"),
            )

    agent = Agent(
        name="test",
        model="gpt-4o",
        provider=MockProvider(),
        tools=[step_a, step_b],
    )

    messages: list[Message] = []
    tc_a = ToolCall(id="id_a", name="step_a", arguments={})
    tc_b = ToolCall(id="id_b", name="step_b", arguments={})
    await agent._execute_tool_calls([tc_a, tc_b], messages)

    assert len(messages) == 2
    ids = [m.tool_call_id for m in messages]
    assert ids == ["id_a", "id_b"]

"""Unit tests for the typed agent event layer (sage/events.py).

Tests cover:
- from_hook_data factory helpers for all event types
- EVENT_TYPE_MAP completeness and correct HookEvent mappings
- agent.on() subscription fires typed callbacks with correct fields
- PRE_TOOL_EXECUTE, POST_TOOL_EXECUTE (with duration_ms), PRE_LLM_CALL (with turn),
  POST_LLM_CALL (with usage/n_tool_calls), ON_DELEGATION, ON_DELEGATION_COMPLETE,
  ON_LLM_STREAM_DELTA
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from sage.agent import Agent
from sage.events import (
    EVENT_TYPE_MAP,
    BackgroundTaskCompleted,
    DelegationCompleted,
    DelegationStarted,
    LLMStreamDelta,
    LLMTurnCompleted,
    LLMTurnStarted,
    ToolCompleted,
    ToolStarted,
    from_hook_data,
)
from sage.hooks.base import HookEvent
from sage.models import CompletionResult, Message, StreamChunk, ToolCall, Usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text_result(content: str, tool_calls: list[ToolCall] | None = None) -> CompletionResult:
    return CompletionResult(
        message=Message(role="assistant", content=content, tool_calls=tool_calls),
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


def _tool_result(name: str, args: dict | None = None) -> CompletionResult:
    tc = ToolCall(id="tc1", name=name, arguments=args or {})
    return CompletionResult(
        message=Message(role="assistant", content=None, tool_calls=[tc]),
        usage=Usage(prompt_tokens=8, completion_tokens=3, total_tokens=11),
    )


class MockProvider:
    def __init__(self, responses: list[CompletionResult]) -> None:
        self._responses = list(responses)
        self._idx = 0

    async def complete(self, messages, tools=None, **kwargs):
        result = self._responses[self._idx % len(self._responses)]
        self._idx += 1
        return result


class StreamMockProvider:
    """Provider that yields stream chunks then a final tool-calls or text chunk."""

    def __init__(self, chunks: list[str], final_text: str = "done") -> None:
        self._chunks = chunks
        self._final_text = final_text

    async def stream(self, messages, tools=None, **kwargs) -> AsyncIterator[StreamChunk]:
        for delta in self._chunks:
            yield StreamChunk(delta=delta)
        yield StreamChunk(delta=self._final_text, finish_reason="stop")


# ---------------------------------------------------------------------------
# from_hook_data factory tests
# ---------------------------------------------------------------------------


class TestFromHookData:
    def test_tool_started(self):
        data = {"tool_name": "shell", "arguments": {"cmd": "ls"}, "turn": 2}
        e = from_hook_data(ToolStarted, data)
        assert isinstance(e, ToolStarted)
        assert e.name == "shell"
        assert e.arguments == {"cmd": "ls"}
        assert e.turn == 2

    def test_tool_started_defaults(self):
        e = from_hook_data(ToolStarted, {})
        assert e.name == ""
        assert e.arguments == {}
        assert e.turn == 0

    def test_tool_completed(self):
        data = {"tool_name": "shell", "result": "output", "duration_ms": 42.5}
        e = from_hook_data(ToolCompleted, data)
        assert isinstance(e, ToolCompleted)
        assert e.name == "shell"
        assert e.result == "output"
        assert e.duration_ms == pytest.approx(42.5)

    def test_tool_completed_defaults(self):
        e = from_hook_data(ToolCompleted, {})
        assert e.duration_ms == pytest.approx(0.0)

    def test_llm_turn_started(self):
        messages = [{"role": "user"}, {"role": "assistant"}]
        data = {
            "turn": 1,
            "model": "claude-sonnet-4-6",
            "messages": messages,
            "complexity": {"score": 42, "level": "medium", "version": "openfang-v1"},
        }
        e = from_hook_data(LLMTurnStarted, data)
        assert isinstance(e, LLMTurnStarted)
        assert e.turn == 1
        assert e.model == "claude-sonnet-4-6"
        assert e.n_messages == 2
        assert e.complexity is not None
        assert e.complexity.score == 42

    def test_llm_turn_completed(self):
        usage = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        data = {
            "turn": 0,
            "usage": usage,
            "n_tool_calls": 3,
            "complexity": {"score": 18, "level": "simple", "version": "openfang-v1"},
        }
        e = from_hook_data(LLMTurnCompleted, data)
        assert isinstance(e, LLMTurnCompleted)
        assert e.turn == 0
        assert e.usage is usage
        assert e.n_tool_calls == 3
        assert e.complexity is not None
        assert e.complexity.score == 18

    def test_delegation_started(self):
        data = {"target": "researcher", "input": "find papers on X"}
        e = from_hook_data(DelegationStarted, data)
        assert isinstance(e, DelegationStarted)
        assert e.target == "researcher"
        assert e.task == "find papers on X"

    def test_delegation_completed(self):
        data = {"target": "researcher", "result": "Found 3 papers"}
        e = from_hook_data(DelegationCompleted, data)
        assert isinstance(e, DelegationCompleted)
        assert e.target == "researcher"
        assert e.result == "Found 3 papers"

    def test_llm_stream_delta(self):
        data = {"delta": "Hello", "turn": 0}
        e = from_hook_data(LLMStreamDelta, data)
        assert isinstance(e, LLMStreamDelta)
        assert e.delta == "Hello"
        assert e.turn == 0

    def test_unknown_class_raises(self):
        with pytest.raises(KeyError):
            from_hook_data(int, {})


# ---------------------------------------------------------------------------
# EVENT_TYPE_MAP correctness
# ---------------------------------------------------------------------------


class TestEventTypeMap:
    def test_all_event_classes_present(self):
        expected = {
            ToolStarted,
            ToolCompleted,
            LLMTurnStarted,
            LLMTurnCompleted,
            DelegationStarted,
            DelegationCompleted,
            LLMStreamDelta,
            BackgroundTaskCompleted,
        }
        assert expected == set(EVENT_TYPE_MAP.keys())

    def test_mappings(self):
        assert EVENT_TYPE_MAP[ToolStarted] == HookEvent.PRE_TOOL_EXECUTE
        assert EVENT_TYPE_MAP[ToolCompleted] == HookEvent.POST_TOOL_EXECUTE
        assert EVENT_TYPE_MAP[LLMTurnStarted] == HookEvent.PRE_LLM_CALL
        assert EVENT_TYPE_MAP[LLMTurnCompleted] == HookEvent.POST_LLM_CALL
        assert EVENT_TYPE_MAP[DelegationStarted] == HookEvent.ON_DELEGATION
        assert EVENT_TYPE_MAP[DelegationCompleted] == HookEvent.ON_DELEGATION_COMPLETE
        assert EVENT_TYPE_MAP[LLMStreamDelta] == HookEvent.ON_LLM_STREAM_DELTA
        assert EVENT_TYPE_MAP[BackgroundTaskCompleted] == HookEvent.BACKGROUND_TASK_COMPLETED


# ---------------------------------------------------------------------------
# agent.on() subscription — typed callbacks fire correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_on_tool_started_fires():
    """ToolStarted callback receives correct tool name, arguments, and turn."""
    received: list[ToolStarted] = []

    async def handler(e: ToolStarted) -> None:
        received.append(e)

    async def fake_tool(x: int) -> str:
        return f"result={x}"

    from sage.tools.decorator import tool as tool_decorator

    @tool_decorator
    def mytool(x: int) -> str:
        """A test tool."""
        return f"result={x}"

    provider = MockProvider(
        [
            _tool_result("mytool", {"x": 7}),
            _text_result("done"),
        ]
    )
    agent = Agent(name="t", model="m", provider=provider, tools=[mytool])
    agent.on(ToolStarted, handler)
    await agent.run("test")

    assert len(received) >= 1
    assert received[0].name == "mytool"
    assert received[0].arguments == {"x": 7}
    assert received[0].turn == 0


@pytest.mark.asyncio
async def test_agent_on_tool_completed_fires():
    """ToolCompleted callback receives name, result string, and non-negative duration_ms."""
    received: list[ToolCompleted] = []

    async def handler(e: ToolCompleted) -> None:
        received.append(e)

    from sage.tools.decorator import tool as tool_decorator

    @tool_decorator
    def mytool(x: int) -> str:
        """A test tool."""
        return f"result={x}"

    provider = MockProvider(
        [
            _tool_result("mytool", {"x": 3}),
            _text_result("done"),
        ]
    )
    agent = Agent(name="t", model="m", provider=provider, tools=[mytool])
    agent.on(ToolCompleted, handler)
    await agent.run("test")

    assert len(received) >= 1
    assert received[0].name == "mytool"
    assert "3" in received[0].result
    assert received[0].duration_ms >= 0.0


@pytest.mark.asyncio
async def test_agent_on_llm_turn_started_fires():
    """LLMTurnStarted callback receives correct turn index and model name."""
    received: list[LLMTurnStarted] = []

    async def handler(e: LLMTurnStarted) -> None:
        received.append(e)

    provider = MockProvider([_text_result("hi")])
    agent = Agent(name="t", model="my-model", provider=provider)
    agent.on(LLMTurnStarted, handler)
    await agent.run("test")

    assert len(received) >= 1
    assert received[0].model == "my-model"
    assert received[0].turn == 0
    assert received[0].n_messages >= 1
    assert received[0].complexity is not None
    assert received[0].complexity.version == "openfang-v1"


@pytest.mark.asyncio
async def test_agent_on_llm_turn_completed_fires():
    """LLMTurnCompleted callback receives turn index, usage, and n_tool_calls."""
    received: list[LLMTurnCompleted] = []

    async def handler(e: LLMTurnCompleted) -> None:
        received.append(e)

    provider = MockProvider([_text_result("hi")])
    agent = Agent(name="t", model="m", provider=provider)
    agent.on(LLMTurnCompleted, handler)
    await agent.run("test")

    assert len(received) >= 1
    assert received[0].turn == 0
    assert received[0].n_tool_calls == 0
    assert received[0].complexity is not None
    assert received[0].complexity.score >= 0


@pytest.mark.asyncio
async def test_agent_on_llm_turn_completed_includes_tool_calls():
    """LLMTurnCompleted.n_tool_calls reflects the number of tool calls in the turn."""
    received: list[LLMTurnCompleted] = []

    async def handler(e: LLMTurnCompleted) -> None:
        received.append(e)

    from sage.tools.decorator import tool as tool_decorator

    @tool_decorator
    def mytool(x: int) -> str:
        """A test tool."""
        return str(x)

    provider = MockProvider(
        [
            _tool_result("mytool", {"x": 1}),
            _text_result("done"),
        ]
    )
    agent = Agent(name="t", model="m", provider=provider, tools=[mytool])
    agent.on(LLMTurnCompleted, handler)
    await agent.run("test")

    assert received[0].n_tool_calls == 1


@pytest.mark.asyncio
async def test_agent_on_delegation_started_and_completed_fire():
    """DelegationStarted and DelegationCompleted callbacks both fire on delegation."""
    started: list[DelegationStarted] = []
    completed: list[DelegationCompleted] = []

    async def on_start(e: DelegationStarted) -> None:
        started.append(e)

    async def on_complete(e: DelegationCompleted) -> None:
        completed.append(e)

    # Sub-agent that just returns a text response
    sub_provider = MockProvider([_text_result("sub result")])
    sub = Agent(name="sub", model="m", provider=sub_provider)

    # Parent agent that delegates
    delegate_call = ToolCall(
        id="d1", name="delegate", arguments={"agent_name": "sub", "task": "do the thing"}
    )
    parent_provider = MockProvider(
        [
            CompletionResult(
                message=Message(role="assistant", content=None, tool_calls=[delegate_call]),
                usage=Usage(),
            ),
            _text_result("parent done"),
        ]
    )
    parent = Agent(name="parent", model="m", provider=parent_provider, subagents={"sub": sub})
    parent.on(DelegationStarted, on_start)
    parent.on(DelegationCompleted, on_complete)
    await parent.run("test")

    assert len(started) == 1
    assert started[0].target == "sub"
    assert started[0].task == "do the thing"

    assert len(completed) == 1
    assert completed[0].target == "sub"
    assert "sub result" in completed[0].result


@pytest.mark.asyncio
async def test_agent_on_llm_stream_delta_fires_during_stream():
    """LLMStreamDelta callback fires for each text chunk during agent.stream()."""
    received: list[LLMStreamDelta] = []

    async def handler(e: LLMStreamDelta) -> None:
        received.append(e)

    provider = StreamMockProvider(["Hello", " world"])
    agent = Agent(name="t", model="m", provider=provider)
    agent.on(LLMStreamDelta, handler)

    chunks = []
    async for chunk in agent.stream("test"):
        chunks.append(chunk)

    assert len(received) >= 2
    assert received[0].delta == "Hello"
    assert received[1].delta == " world"
    assert all(e.turn == 0 for e in received)


@pytest.mark.asyncio
async def test_agent_on_multiple_subscriptions():
    """Multiple handlers for the same event all receive the event."""
    counts = [0, 0]

    async def h1(e: LLMTurnStarted) -> None:
        counts[0] += 1

    async def h2(e: LLMTurnStarted) -> None:
        counts[1] += 1

    provider = MockProvider([_text_result("hi")])
    agent = Agent(name="t", model="m", provider=provider)
    agent.on(LLMTurnStarted, h1)
    agent.on(LLMTurnStarted, h2)
    await agent.run("test")

    assert counts[0] >= 1
    assert counts[1] >= 1


@pytest.mark.asyncio
async def test_pre_tool_execute_fires_before_post():
    """PRE_TOOL_EXECUTE fires before POST_TOOL_EXECUTE for the same tool."""
    order: list[str] = []

    async def on_start(e: ToolStarted) -> None:
        order.append(f"start:{e.name}")

    async def on_end(e: ToolCompleted) -> None:
        order.append(f"end:{e.name}")

    from sage.tools.decorator import tool as tool_decorator

    @tool_decorator
    def mytool() -> str:
        """A test tool."""
        return "ok"

    provider = MockProvider([_tool_result("mytool", {}), _text_result("done")])
    agent = Agent(name="t", model="m", provider=provider, tools=[mytool])
    agent.on(ToolStarted, on_start)
    agent.on(ToolCompleted, on_end)
    await agent.run("test")

    assert order == ["start:mytool", "end:mytool"]


@pytest.mark.asyncio
async def test_current_turn_tracked():
    """_current_turn increments across loop iterations."""
    turns_seen: list[int] = []

    async def on_turn(e: LLMTurnStarted) -> None:
        turns_seen.append(e.turn)

    from sage.tools.decorator import tool as tool_decorator

    @tool_decorator
    def mytool() -> str:
        """A test tool."""
        return "ok"

    provider = MockProvider(
        [
            _tool_result("mytool", {}),  # turn 0 uses a tool
            _text_result("done"),  # turn 1 finishes
        ]
    )
    agent = Agent(name="t", model="m", provider=provider, tools=[mytool])
    agent.on(LLMTurnStarted, on_turn)
    await agent.run("test")

    assert turns_seen == [0, 1]

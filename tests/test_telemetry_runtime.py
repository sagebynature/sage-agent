from __future__ import annotations

import pytest

from sage.agent import Agent
from sage.hooks.base import HookEvent
from sage.hooks.builtin.follow_through import make_follow_through_hook
from sage.hooks.registry import HookRegistry
from sage.models import CompletionResult, Message, ToolCall, Usage


class RecordingProvider:
    def __init__(self, responses: list[CompletionResult]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    async def complete(self, messages, tools=None, **kwargs):
        self.calls.append(
            {
                "messages": list(messages),
                "tools": tools,
                "kwargs": dict(kwargs),
            }
        )
        return self.responses.pop(0)


def _text_result(content: str) -> CompletionResult:
    return CompletionResult(
        message=Message(role="assistant", content=content),
        usage=Usage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
    )


@pytest.mark.asyncio
async def test_pre_llm_modifying_hook_changes_live_provider_request() -> None:
    provider = RecordingProvider([_text_result("done")])
    hooks = HookRegistry()

    async def mutate_request(event: HookEvent, data: dict[str, object]) -> dict[str, object] | None:
        if event != HookEvent.PRE_LLM_CALL:
            return None
        messages = list(data["messages"])  # type: ignore[index]
        messages.insert(0, Message(role="system", content="Injected"))
        data["messages"] = messages
        data["model"] = "alt-model"
        return data

    hooks.register(HookEvent.PRE_LLM_CALL, mutate_request, modifying=True)
    agent = Agent(name="t", model="base-model", provider=provider, hook_registry=hooks)

    result = await agent.run("hello")

    assert result == "done"
    assert provider.calls[0]["kwargs"]["model"] == "alt-model"
    provider_messages = provider.calls[0]["messages"]
    assert isinstance(provider_messages, list)
    assert provider_messages[0].content == "Injected"


@pytest.mark.asyncio
async def test_post_llm_modifying_hook_can_retry_live_turn() -> None:
    provider = RecordingProvider(
        [
            _text_result("I cannot do that for you."),
            _text_result("completed action"),
        ]
    )
    hooks = HookRegistry()
    hooks.register(HookEvent.POST_LLM_CALL, make_follow_through_hook(max_retries=1), modifying=True)
    agent = Agent(name="t", model="m", provider=provider, hook_registry=hooks)

    result = await agent.run("do it")

    assert result == "completed action"
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_post_tool_hook_changes_tool_result_seen_by_model_and_telemetry() -> None:
    provider = RecordingProvider(
        [
            CompletionResult(
                message=Message(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        ToolCall(id="call-1", name="secret_tool", arguments={}),
                    ],
                ),
                usage=Usage(),
            ),
            _text_result("done"),
        ]
    )
    hooks = HookRegistry()

    async def scrub_result(event: HookEvent, data: dict[str, object]) -> None:
        if event == HookEvent.POST_TOOL_EXECUTE and isinstance(data.get("result"), str):
            data["result"] = "scrubbed"

    hooks.register(HookEvent.POST_TOOL_EXECUTE, scrub_result)

    from sage.tools.decorator import tool

    @tool
    def secret_tool() -> str:
        """Return a fake secret."""
        return "sk-secret-value-1234567890"

    agent = Agent(name="t", model="m", provider=provider, hook_registry=hooks, tools=[secret_tool])

    result = await agent.run("test")

    assert result == "done"
    second_call_messages = provider.calls[1]["messages"]
    assert isinstance(second_call_messages, list)
    tool_messages = [m for m in second_call_messages if m.role == "tool"]
    assert tool_messages
    assert tool_messages[0].content == "scrubbed"

    post_tool_events = [
        event
        for event in agent._telemetry_recorder.events
        if event.event_name == HookEvent.POST_TOOL_EXECUTE.value
    ]
    assert post_tool_events
    assert post_tool_events[0].payload["result"] == "scrubbed"


@pytest.mark.asyncio
async def test_tool_events_include_real_tool_call_ids_for_repeated_tool_names() -> None:
    provider = RecordingProvider(
        [
            CompletionResult(
                message=Message(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        ToolCall(id="call-a", name="echo_tool", arguments={"value": "a"}),
                        ToolCall(id="call-b", name="echo_tool", arguments={"value": "b"}),
                    ],
                ),
                usage=Usage(),
            ),
            _text_result("done"),
        ]
    )

    from sage.tools.decorator import tool

    @tool
    def echo_tool(value: str) -> str:
        """Echo a value."""
        return value

    agent = Agent(name="t", model="m", provider=provider, tools=[echo_tool])
    await agent.run("test")

    started = [
        event.payload["tool_call_id"]
        for event in agent._telemetry_recorder.events
        if event.event_name == HookEvent.PRE_TOOL_EXECUTE.value
    ]
    completed = [
        event.payload["tool_call_id"]
        for event in agent._telemetry_recorder.events
        if event.event_name == HookEvent.POST_TOOL_EXECUTE.value
    ]

    assert started == ["call-a", "call-b"]
    assert completed == ["call-a", "call-b"]

from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from sage.events import (
    BackgroundTaskCompleted,
    DelegationCompleted,
    DelegationStarted,
    LLMStreamDelta,
    LLMTurnCompleted,
    LLMTurnStarted,
    ToolCompleted,
    ToolStarted,
)
from sage.models import Usage
from sage.protocol.bridge import EventBridge

EventHandler = Callable[[object], Awaitable[None]]


def _setup_bridge() -> tuple[EventBridge, MagicMock, MagicMock, dict[type[object], EventHandler]]:
    mock_server = MagicMock()
    mock_server.send_notification = AsyncMock()

    mock_agent = MagicMock()
    handlers: dict[type[object], EventHandler] = {}

    def mock_on(event_class: type[object], handler: EventHandler) -> None:
        handlers[event_class] = handler

    mock_agent.on = mock_on
    mock_agent.name = "root"
    mock_agent.model = "gpt-4o"
    mock_agent.cumulative_usage = Usage(prompt_tokens=11, completion_tokens=7, cost=0.42)

    bridge = EventBridge(server=mock_server, agent=mock_agent)
    bridge.setup()
    return bridge, mock_server, mock_agent, handlers


@pytest.mark.asyncio
async def test_stream_delta_sends_notification() -> None:
    _, mock_server, _, handlers = _setup_bridge()

    await handlers[LLMStreamDelta](LLMStreamDelta(delta="hello", turn=0))

    mock_server.send_notification.assert_awaited_once_with(
        "stream/delta",
        {"delta": "hello", "turn": 0, "agent_path": ["root"]},
    )


@pytest.mark.asyncio
async def test_tool_started_sends_notification() -> None:
    _, mock_server, _, handlers = _setup_bridge()

    event = ToolStarted(name="shell", arguments={"command": "ls"}, turn=2)
    await handlers[ToolStarted](event)

    mock_server.send_notification.assert_awaited_once_with(
        "tool/started",
        {
            "toolName": "shell",
            "callId": "call_2_shell",
            "arguments": {"command": "ls"},
            "agent_path": ["root"],
        },
    )


@pytest.mark.asyncio
async def test_tool_completed_sends_notification() -> None:
    _, mock_server, _, handlers = _setup_bridge()

    event = ToolCompleted(name="shell", result="ok", duration_ms=12.5)
    await handlers[ToolCompleted](event)

    mock_server.send_notification.assert_awaited_once_with(
        "tool/completed",
        {
            "toolName": "shell",
            "callId": "call_0_shell",
            "result": "ok",
            "durationMs": 12.5,
            "error": None,
            "agent_path": ["root"],
        },
    )


@pytest.mark.asyncio
async def test_turn_started_sends_notification() -> None:
    _, mock_server, _, handlers = _setup_bridge()

    event = LLMTurnStarted(turn=3, model="gpt-4o", n_messages=4)
    await handlers[LLMTurnStarted](event)

    mock_server.send_notification.assert_awaited_once_with(
        "turn/started",
        {"turn": 3, "model": "gpt-4o", "agent_path": ["root"]},
    )


@pytest.mark.asyncio
async def test_turn_completed_sends_notification_with_usage() -> None:
    _, mock_server, _, handlers = _setup_bridge()

    usage = Usage(prompt_tokens=10, completion_tokens=5, cost=0.15)
    event = LLMTurnCompleted(turn=1, usage=usage, n_tool_calls=0)
    await handlers[LLMTurnCompleted](event)

    first_call = mock_server.send_notification.await_args_list[0]
    assert first_call.args == (
        "turn/completed",
        {
            "turn": 1,
            "usage": {"input": 10, "output": 5, "cost": 0.15},
            "agent_path": ["root"],
        },
    )


@pytest.mark.asyncio
async def test_delegation_started_sends_notification() -> None:
    _, mock_server, _, handlers = _setup_bridge()

    event = DelegationStarted(target="researcher", task="find papers")
    await handlers[DelegationStarted](event)

    mock_server.send_notification.assert_awaited_once_with(
        "delegation/started",
        {
            "agentName": "researcher",
            "task": "find papers",
            "depth": 1,
            "agent_path": ["root", "researcher"],
        },
    )


@pytest.mark.asyncio
async def test_delegation_completed_truncates_result() -> None:
    _, mock_server, _, handlers = _setup_bridge()

    long_result = "x" * 1400
    event = DelegationCompleted(target="helper", result=long_result)
    await handlers[DelegationCompleted](event)

    expected_result = "x" * 1000
    mock_server.send_notification.assert_awaited_once_with(
        "delegation/completed",
        {
            "agentName": "helper",
            "result": expected_result,
            "duration": 0,
            "agent_path": ["root"],
        },
    )


@pytest.mark.asyncio
async def test_background_completed_sends_notification() -> None:
    _, mock_server, _, handlers = _setup_bridge()

    event = BackgroundTaskCompleted(
        task_id="task-1",
        agent_name="researcher",
        status="completed",
        result="done",
        error=None,
    )
    await handlers[BackgroundTaskCompleted](event)

    mock_server.send_notification.assert_awaited_once_with(
        "background/completed",
        {
            "taskId": "task-1",
            "agentName": "researcher",
            "status": "completed",
            "result": "done",
            "error": None,
            "agent_path": ["background", "task-1"],
        },
    )


@pytest.mark.asyncio
async def test_handler_error_is_logged_and_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    _, mock_server, _, handlers = _setup_bridge()
    mock_server.send_notification.side_effect = RuntimeError("boom")

    with caplog.at_level("ERROR"):
        await handlers[LLMStreamDelta](LLMStreamDelta(delta="oops", turn=0))

    assert "Bridge error: boom" in caplog.text


@pytest.mark.asyncio
async def test_usage_update_includes_context_usage_percent() -> None:
    """usage/update should include computed contextUsagePercent, not hardcoded 0."""
    bridge, mock_server, mock_agent, _ = _setup_bridge()

    # Remove cumulative_usage so _extract_usage_stats falls through to get_usage_stats
    del mock_agent.cumulative_usage

    # Mock get_usage_stats to return a usage_percentage
    mock_agent.get_usage_stats = MagicMock(return_value={
        "cumulative_prompt_tokens": 1000,
        "cumulative_completion_tokens": 500,
        "cumulative_cost": 0.05,
        "usage_percentage": 0.42,
    })
    mock_agent.model = "test-model"

    await bridge._send_usage_update()

    mock_server.send_notification.assert_called_once()
    call_args = mock_server.send_notification.call_args
    assert call_args[0][0] == "usage/update"
    payload = call_args[0][1]
    assert payload["contextUsagePercent"] == 42  # 0.42 * 100


@pytest.mark.asyncio
async def test_usage_update_sent_after_turn_completed() -> None:
    _, mock_server, _, handlers = _setup_bridge()

    usage = Usage(prompt_tokens=2, completion_tokens=3, cost=0.01)
    event = LLMTurnCompleted(turn=0, usage=usage, n_tool_calls=0)
    await handlers[LLMTurnCompleted](event)

    assert len(mock_server.send_notification.await_args_list) == 2
    second_call = mock_server.send_notification.await_args_list[1]
    assert second_call.args == (
        "usage/update",
        {
            "promptTokens": 11,
            "completionTokens": 7,
            "totalCost": 0.42,
            "model": "gpt-4o",
            "contextUsagePercent": 0,
            "agent_path": ["root"],
        },
    )

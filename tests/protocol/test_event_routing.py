from __future__ import annotations

import asyncio
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


def _setup_bridge(
    root_name: str = "root",
) -> tuple[EventBridge, MagicMock, dict[type[object], EventHandler]]:
    mock_server = MagicMock()
    mock_server.send_notification = AsyncMock()

    mock_agent = MagicMock()
    mock_agent.name = root_name
    mock_agent.model = "gpt-4o"
    mock_agent.cumulative_usage = Usage(prompt_tokens=1, completion_tokens=2, cost=0.03)

    handlers: dict[type[object], EventHandler] = {}

    def mock_on(event_class: type[object], handler: EventHandler) -> None:
        handlers[event_class] = handler

    mock_agent.on = mock_on

    bridge = EventBridge(server=mock_server, agent=mock_agent)
    bridge.setup()
    return bridge, mock_server, handlers


@pytest.mark.asyncio
async def test_root_level_events_include_root_agent_path() -> None:
    _, mock_server, handlers = _setup_bridge(root_name="orchestrator")

    await handlers[LLMStreamDelta](LLMStreamDelta(delta="hello", turn=0))

    payload = mock_server.send_notification.await_args.args[1]
    assert payload["agent_path"] == ["orchestrator"]


@pytest.mark.asyncio
async def test_single_delegation_routes_events_with_child_path() -> None:
    _, mock_server, handlers = _setup_bridge(root_name="root")

    await handlers[DelegationStarted](DelegationStarted(target="child", task="work"))
    await handlers[LLMStreamDelta](LLMStreamDelta(delta="chunk", turn=1))

    started_payload = mock_server.send_notification.await_args_list[0].args[1]
    delta_payload = mock_server.send_notification.await_args_list[1].args[1]
    assert started_payload["agent_path"] == ["root", "child"]
    assert delta_payload["agent_path"] == ["root", "child"]


@pytest.mark.asyncio
async def test_nested_delegation_depth_three_updates_path_per_level() -> None:
    _, mock_server, handlers = _setup_bridge(root_name="root")

    await handlers[DelegationStarted](DelegationStarted(target="child", task="step1"))
    await handlers[DelegationStarted](DelegationStarted(target="grandchild", task="step2"))
    await handlers[LLMStreamDelta](LLMStreamDelta(delta="in-grandchild", turn=2))

    first_started = mock_server.send_notification.await_args_list[0].args[1]
    second_started = mock_server.send_notification.await_args_list[1].args[1]
    stream_payload = mock_server.send_notification.await_args_list[2].args[1]
    assert first_started["agent_path"] == ["root", "child"]
    assert second_started["agent_path"] == ["root", "child", "grandchild"]
    assert stream_payload["agent_path"] == ["root", "child", "grandchild"]


@pytest.mark.asyncio
async def test_delegation_completed_pops_path_back_to_parent() -> None:
    _, mock_server, handlers = _setup_bridge(root_name="root")

    await handlers[DelegationStarted](DelegationStarted(target="child", task="work"))
    await handlers[DelegationCompleted](DelegationCompleted(target="child", result="done"))
    await handlers[ToolStarted](ToolStarted(name="shell", arguments={"command": "pwd"}, turn=1))

    completed_payload = mock_server.send_notification.await_args_list[1].args[1]
    root_tool_payload = mock_server.send_notification.await_args_list[2].args[1]
    assert completed_payload["agent_path"] == ["root"]
    assert root_tool_payload["agent_path"] == ["root"]


@pytest.mark.asyncio
async def test_parallel_delegations_have_isolated_paths_per_task() -> None:
    _, mock_server, handlers = _setup_bridge(root_name="root")

    stream_paths: dict[str, list[str]] = {}

    async def capture_notification(method: str, payload: dict[str, object]) -> None:
        if method == "stream/delta":
            stream_paths[str(payload["delta"])] = list(payload["agent_path"])
        await asyncio.sleep(0)

    mock_server.send_notification.side_effect = capture_notification

    async def run_branch(child_name: str) -> None:
        await handlers[DelegationStarted](DelegationStarted(target=child_name, task="work"))
        await asyncio.sleep(0)
        await handlers[LLMStreamDelta](LLMStreamDelta(delta=child_name, turn=1))
        await handlers[DelegationCompleted](DelegationCompleted(target=child_name, result="done"))

    await asyncio.gather(run_branch("child-a"), run_branch("child-b"))

    assert stream_paths["child-a"] == ["root", "child-a"]
    assert stream_paths["child-b"] == ["root", "child-b"]


@pytest.mark.asyncio
async def test_background_completed_uses_background_task_path() -> None:
    _, mock_server, handlers = _setup_bridge(root_name="root")

    await handlers[DelegationStarted](DelegationStarted(target="child", task="work"))
    await handlers[BackgroundTaskCompleted](
        BackgroundTaskCompleted(
            task_id="task-9",
            agent_name="child",
            status="completed",
            result="ok",
            error=None,
        )
    )

    background_payload = mock_server.send_notification.await_args_list[1].args[1]
    assert background_payload["agent_path"] == ["background", "task-9"]


@pytest.mark.asyncio
async def test_turn_completed_emits_agent_path_on_both_notifications() -> None:
    _, mock_server, handlers = _setup_bridge(root_name="root")

    await handlers[LLMTurnStarted](LLMTurnStarted(turn=0, model="gpt-4o", n_messages=2))
    await handlers[LLMTurnCompleted](
        LLMTurnCompleted(
            turn=0, usage=Usage(prompt_tokens=2, completion_tokens=1, cost=0.02), n_tool_calls=0
        )
    )

    turn_started = mock_server.send_notification.await_args_list[0].args[1]
    turn_completed = mock_server.send_notification.await_args_list[1].args[1]
    usage_update = mock_server.send_notification.await_args_list[2].args[1]
    assert turn_started["agent_path"] == ["root"]
    assert turn_completed["agent_path"] == ["root"]
    assert usage_update["agent_path"] == ["root"]


@pytest.mark.asyncio
async def test_agent_path_payload_is_copy_not_mutable_reference() -> None:
    _, mock_server, handlers = _setup_bridge(root_name="root")

    await handlers[DelegationStarted](DelegationStarted(target="child", task="work"))
    await handlers[ToolCompleted](ToolCompleted(name="ls", result="ok", duration_ms=1.2))
    first_payload = mock_server.send_notification.await_args_list[1].args[1]
    first_payload["agent_path"].append("tampered")

    await handlers[LLMStreamDelta](LLMStreamDelta(delta="next", turn=1))
    second_payload = mock_server.send_notification.await_args_list[2].args[1]
    assert second_payload["agent_path"] == ["root", "child"]

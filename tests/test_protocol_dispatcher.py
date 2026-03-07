from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from sage.models import ToolSchema
from sage.protocol.dispatcher import MethodDispatcher


def _make_server() -> MagicMock:
    server = MagicMock()
    server._success_response.side_effect = lambda request_id, result: {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }
    server._error_response.side_effect = lambda request_id, code, message: {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
    return server


def _make_dispatcher() -> tuple[MethodDispatcher, MagicMock, MagicMock, MagicMock]:
    agent = MagicMock()
    agent.run = AsyncMock(return_value="hello")
    agent.model = "gpt-4o"
    agent.temperature = 0.2
    agent.tool_registry = MagicMock()
    agent.tool_registry.get_schemas.return_value = [
        ToolSchema(
            name="search",
            description="search docs",
            parameters={"type": "object", "properties": {}},
        )
    ]

    session_manager = MagicMock()
    session_manager.list_sessions.return_value = [{"id": "s1"}]
    session_manager.get_session.return_value = {"id": "s1", "messages": []}
    session_manager.destroy_session.return_value = True

    server = _make_server()
    return (
        MethodDispatcher(agent=agent, session_manager=session_manager, server=server),
        agent,
        session_manager,
        server,
    )


@pytest.mark.asyncio
async def test_dispatch_routes_to_registered_handler() -> None:
    dispatcher, _agent, _session_manager, _server = _make_dispatcher()
    handler = AsyncMock(return_value={"ok": True})
    dispatcher.register("custom/method", handler)

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "custom/method",
            "params": {"x": 1},
        }
    )

    assert response["result"] == {"ok": True}
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_agent_run_returns_started_with_run_id() -> None:
    dispatcher, _agent, _session_manager, _server = _make_dispatcher()

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "agent/run",
            "params": {"message": "hello"},
        }
    )

    assert response["result"]["status"] == "started"
    assert "runId" in response["result"]
    UUID(response["result"]["runId"])


@pytest.mark.asyncio
async def test_agent_cancel_returns_success() -> None:
    dispatcher, _agent, _session_manager, _server = _make_dispatcher()
    await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "agent/run",
            "params": {"message": "hello"},
        }
    )

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "agent/cancel",
            "params": {},
        }
    )

    assert response["result"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_session_list_returns_sessions() -> None:
    dispatcher, _agent, session_manager, _server = _make_dispatcher()

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "session/list",
            "params": {},
        }
    )

    session_manager.list_sessions.assert_called_once()
    assert response["result"]["sessions"] == [{"id": "s1"}]


@pytest.mark.asyncio
async def test_session_resume_returns_session_data() -> None:
    dispatcher, _agent, session_manager, _server = _make_dispatcher()

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "session/resume",
            "params": {"session_id": "s1"},
        }
    )

    session_manager.get_session.assert_called_once_with("s1")
    assert response["result"]["session"]["id"] == "s1"


@pytest.mark.asyncio
async def test_session_clear_returns_success() -> None:
    dispatcher, _agent, session_manager, _server = _make_dispatcher()

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "session/clear",
            "params": {"session_id": "s1"},
        }
    )

    session_manager.destroy_session.assert_called_once_with("s1")
    assert response["result"] == {"cleared": True}


@pytest.mark.asyncio
async def test_config_get_returns_config_value() -> None:
    dispatcher, _agent, _session_manager, _server = _make_dispatcher()

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "config/get",
            "params": {"key": "model"},
        }
    )

    assert response["result"] == {"key": "model", "value": "gpt-4o"}


@pytest.mark.asyncio
async def test_config_set_updates_config() -> None:
    dispatcher, agent, _session_manager, _server = _make_dispatcher()

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "config/set",
            "params": {"key": "model", "value": "gpt-4o-mini"},
        }
    )

    assert agent.model == "gpt-4o-mini"
    assert response["result"] == {"key": "model", "value": "gpt-4o-mini"}


@pytest.mark.asyncio
async def test_tools_list_returns_tool_schemas() -> None:
    dispatcher, _agent, _session_manager, _server = _make_dispatcher()

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/list",
            "params": {},
        }
    )

    tools = response["result"]["tools"]
    assert len(tools) == 1
    assert tools[0]["name"] == "search"


@pytest.mark.asyncio
async def test_permission_respond_resolves_future() -> None:
    dispatcher, _agent, _session_manager, _server = _make_dispatcher()
    future = dispatcher.create_permission_future("perm-1")

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "permission/respond",
            "params": {"request_id": "perm-1", "decision": "allow"},
        }
    )

    assert future.done()
    assert future.result() == {"request_id": "perm-1", "decision": "allow"}
    assert response["result"] == {"resolved": True}


@pytest.mark.asyncio
async def test_unknown_method_returns_method_not_found() -> None:
    dispatcher, _agent, _session_manager, _server = _make_dispatcher()

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "missing/method",
            "params": {},
        }
    )

    assert response["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_internal_error_returns_internal_error_code() -> None:
    dispatcher, _agent, _session_manager, _server = _make_dispatcher()

    async def broken(_request: dict) -> dict:
        raise RuntimeError("boom")

    dispatcher.register("broken/method", broken)

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "broken/method",
            "params": {},
        }
    )

    assert response["error"]["code"] == -32603


@pytest.mark.asyncio
async def test_invalid_params_returns_invalid_params_error() -> None:
    dispatcher, _agent, _session_manager, _server = _make_dispatcher()

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 14,
            "method": "agent/run",
            "params": {"message": 123},
        }
    )

    assert response["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_permission_respond_missing_future_returns_not_resolved() -> None:
    dispatcher, _agent, _session_manager, _server = _make_dispatcher()

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 15,
            "method": "permission/respond",
            "params": {"request_id": "missing", "decision": "deny"},
        }
    )

    assert response["result"] == {"resolved": False}


@pytest.mark.asyncio
async def test_agent_methods_error_when_agent_missing() -> None:
    _dispatcher, _agent, session_manager, server = _make_dispatcher()
    dispatcher = MethodDispatcher(agent=None, session_manager=session_manager, server=server)

    response = await dispatcher.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 16,
            "method": "agent/run",
            "params": {"message": "hello"},
        }
    )

    assert response["error"]["code"] == -32603


@pytest.mark.asyncio
async def test_agent_run_uses_stream_not_run() -> None:
    """agent/run should call agent.stream(), not agent.run()."""
    dispatcher, agent, _session_manager, server = _make_dispatcher()

    async def fake_stream(message: str):
        yield "hello "
        yield "world"

    agent.stream = MagicMock(side_effect=fake_stream)
    server.send_notification = AsyncMock()

    response = await dispatcher.dispatch(
        {"jsonrpc": "2.0", "id": 20, "method": "agent/run", "params": {"message": "hi"}}
    )

    assert response["result"]["status"] == "started"
    await asyncio.sleep(0.1)
    agent.stream.assert_called_once_with("hi")


@pytest.mark.asyncio
async def test_agent_run_sends_completed_notification() -> None:
    """When streaming finishes, dispatcher sends run/completed notification."""
    dispatcher, agent, _session_manager, server = _make_dispatcher()

    async def fake_stream(message: str):
        yield "done"

    agent.stream = MagicMock(side_effect=fake_stream)
    server.send_notification = AsyncMock()

    await dispatcher.dispatch(
        {"jsonrpc": "2.0", "id": 21, "method": "agent/run", "params": {"message": "hi"}}
    )
    await asyncio.sleep(0.1)

    calls = server.send_notification.await_args_list
    completed_calls = [c for c in calls if c.args[0] == "run/completed"]
    assert len(completed_calls) == 1
    payload = completed_calls[0].args[1]
    assert payload["status"] == "success"
    assert "runId" in payload


@pytest.mark.asyncio
async def test_permission_handler_integration() -> None:
    """JsonRpcPermissionHandler can be created with server and dispatcher."""
    from sage.protocol.permissions import JsonRpcPermissionHandler

    dispatcher, _agent, _session_manager, server = _make_dispatcher()
    handler = JsonRpcPermissionHandler(server=server, dispatcher=dispatcher)
    assert handler is not None
    assert hasattr(dispatcher, "pending_permissions")
    assert hasattr(dispatcher, "create_permission_future")


@pytest.mark.asyncio
async def test_agent_run_sends_error_on_failure() -> None:
    """When streaming raises, dispatcher sends run/completed with error."""
    dispatcher, agent, _session_manager, server = _make_dispatcher()

    async def failing_stream(message: str):
        raise RuntimeError("model error")
        yield  # make it a generator

    agent.stream = MagicMock(side_effect=failing_stream)
    server.send_notification = AsyncMock()

    await dispatcher.dispatch(
        {"jsonrpc": "2.0", "id": 22, "method": "agent/run", "params": {"message": "hi"}}
    )
    await asyncio.sleep(0.1)

    calls = server.send_notification.await_args_list
    completed_calls = [c for c in calls if c.args[0] == "run/completed"]
    assert len(completed_calls) == 1
    payload = completed_calls[0].args[1]
    assert payload["status"] == "error"
    assert "model error" in payload["error"]

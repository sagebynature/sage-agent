from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from sage.permissions.base import PermissionAction
from sage.protocol.permissions import JsonRpcPermissionHandler


def _make_handler(
    *,
    timeout: float = 1.0,
) -> tuple[JsonRpcPermissionHandler, AsyncMock, MagicMock]:
    server = MagicMock()
    server.send_notification = AsyncMock()

    dispatcher = MagicMock()
    dispatcher.pending_permissions = {}

    def create_permission_future(request_id: str) -> asyncio.Future[dict[str, str]]:
        future: asyncio.Future[dict[str, str]] = asyncio.get_running_loop().create_future()
        dispatcher.pending_permissions[request_id] = future
        return future

    dispatcher.create_permission_future = MagicMock(side_effect=create_permission_future)
    return (
        JsonRpcPermissionHandler(server, dispatcher, timeout=timeout),
        server.send_notification,
        dispatcher,
    )


@pytest.mark.asyncio
async def test_allow_once() -> None:
    handler, send_notification, dispatcher = _make_handler(timeout=1.0)

    check_task = asyncio.create_task(handler.check("shell", {"command": "ls"}))
    await asyncio.sleep(0)

    request_id = send_notification.call_args[0][1]["id"]
    dispatcher.pending_permissions[request_id].set_result({"decision": "allow_once"})

    result = await check_task
    assert result.action == PermissionAction.ALLOW
    assert result.reason is None

    send_notification.assert_awaited_once()
    method, params = send_notification.call_args[0]
    assert method == "permission/request"
    assert params["tool"] == "shell"
    assert params["arguments"] == {"command": "ls"}
    assert params["riskLevel"] == "high"


@pytest.mark.asyncio
async def test_allow_always() -> None:
    handler, send_notification, dispatcher = _make_handler(timeout=1.0)

    first = asyncio.create_task(handler.check("shell", {"command": "pwd"}))
    await asyncio.sleep(0)
    first_request_id = send_notification.call_args[0][1]["id"]
    dispatcher.pending_permissions[first_request_id].set_result({"decision": "allow_always"})

    first_result = await first
    assert first_result.action == PermissionAction.ALLOW

    second_result = await handler.check("shell", {"command": "whoami"})
    assert second_result.action == PermissionAction.ALLOW
    assert second_result.reason == "Session-scoped approval"
    assert send_notification.await_count == 1


@pytest.mark.asyncio
async def test_allow_session() -> None:
    handler, send_notification, dispatcher = _make_handler(timeout=1.0)

    first_args = {"command": "git status"}
    first = asyncio.create_task(handler.check("shell", first_args))
    await asyncio.sleep(0)
    request_id = send_notification.call_args[0][1]["id"]
    dispatcher.pending_permissions[request_id].set_result({"decision": "allow_session"})

    first_result = await first
    assert first_result.action == PermissionAction.ALLOW

    second_result = await handler.check("shell", first_args)
    assert second_result.action == PermissionAction.ALLOW
    assert second_result.reason == "Session-scoped approval"
    assert send_notification.await_count == 1

    third_result = asyncio.create_task(handler.check("shell", {"command": "git diff"}))
    await asyncio.sleep(0)
    assert send_notification.await_count == 2
    third_request_id = send_notification.call_args_list[-1][0][1]["id"]
    dispatcher.pending_permissions[third_request_id].set_result({"decision": "deny"})
    denied = await third_result
    assert denied.action == PermissionAction.DENY


@pytest.mark.asyncio
async def test_deny() -> None:
    handler, send_notification, dispatcher = _make_handler(timeout=1.0)

    task = asyncio.create_task(handler.check("file_write", {"path": "/tmp/x.txt"}))
    await asyncio.sleep(0)
    request_id = send_notification.call_args[0][1]["id"]
    dispatcher.pending_permissions[request_id].set_result(
        {"decision": "deny", "reason": "Not permitted by user"}
    )

    result = await task
    assert result.action == PermissionAction.DENY
    assert result.reason == "Not permitted by user"


@pytest.mark.asyncio
async def test_edit_decision() -> None:
    handler, send_notification, dispatcher = _make_handler(timeout=1.0)

    task = asyncio.create_task(handler.check("shell", {"command": "rm file.txt"}))
    await asyncio.sleep(0)
    request_id = send_notification.call_args[0][1]["id"]
    dispatcher.pending_permissions[request_id].set_result(
        {
            "decision": "edit",
            "editedArgs": {"command": "rm -i file.txt"},
        }
    )

    result = await task
    assert result.action == PermissionAction.ALLOW
    assert result.reason == "Allowed with edits"


@pytest.mark.asyncio
async def test_timeout() -> None:
    handler, _send_notification, dispatcher = _make_handler(timeout=0.01)

    result = await handler.check("shell", {"command": "sleep 1"})
    assert result.action == PermissionAction.DENY
    assert "timed out" in (result.reason or "")
    assert dispatcher.pending_permissions == {}


@pytest.mark.asyncio
async def test_session_reset() -> None:
    handler, send_notification, dispatcher = _make_handler(timeout=1.0)

    first = asyncio.create_task(handler.check("shell", {"command": "ls"}))
    await asyncio.sleep(0)
    first_request_id = send_notification.call_args[0][1]["id"]
    dispatcher.pending_permissions[first_request_id].set_result({"decision": "allow_session"})
    await first

    cached = await handler.check("shell", {"command": "ls"})
    assert cached.action == PermissionAction.ALLOW
    assert send_notification.await_count == 1

    handler.reset_session("new-session")

    second = asyncio.create_task(handler.check("shell", {"command": "ls"}))
    await asyncio.sleep(0)
    assert send_notification.await_count == 2
    second_request_id = send_notification.call_args_list[-1][0][1]["id"]
    dispatcher.pending_permissions[second_request_id].set_result({"decision": "allow_once"})
    await second


@pytest.mark.asyncio
async def test_race_condition() -> None:
    handler, send_notification, dispatcher = _make_handler(timeout=1.0)

    tasks = [
        asyncio.create_task(handler.check("shell", {"command": "ls"})),
        asyncio.create_task(handler.check("shell", {"command": "pwd"})),
        asyncio.create_task(handler.check("file_read", {"path": "README.md"})),
    ]

    for _ in range(100):
        if send_notification.await_count == 3:
            break
        await asyncio.sleep(0.001)
    assert send_notification.await_count == 3

    ids = [call[0][1]["id"] for call in send_notification.call_args_list]
    dispatcher.pending_permissions[ids[0]].set_result({"decision": "allow_once"})
    dispatcher.pending_permissions[ids[1]].set_result({"decision": "deny", "reason": "Nope"})
    dispatcher.pending_permissions[ids[2]].set_result({"decision": "allow_once"})

    results = await asyncio.gather(*tasks)
    assert [result.action for result in results] == [
        PermissionAction.ALLOW,
        PermissionAction.DENY,
        PermissionAction.ALLOW,
    ]
    assert results[1].reason == "Nope"


def test_risk_assessment() -> None:
    assert JsonRpcPermissionHandler._assess_risk("shell", {"command": "ls"}) == "high"
    assert JsonRpcPermissionHandler._assess_risk("file_read", {"path": "a.txt"}) == "medium"
    assert JsonRpcPermissionHandler._assess_risk("unknown_tool", {}) == "low"


def test_critical_risk() -> None:
    assert (
        JsonRpcPermissionHandler._assess_risk("shell", {"command": "rm -rf /tmp/test"})
        == "critical"
    )

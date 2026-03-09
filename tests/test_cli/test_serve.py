from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sage.cli.serve import _serve
from sage.permissions.allow_all import AllowAllPermissionHandler


@pytest.mark.asyncio
async def test_serve_yolo_installs_allow_all_permission_handler() -> None:
    server = MagicMock()
    server.set_dispatcher = MagicMock()
    server.start = AsyncMock()

    dispatcher = MagicMock()
    session_manager = MagicMock()
    bridge = MagicMock()
    bridge.setup = MagicMock()

    mock_agent = MagicMock()
    mock_agent.tool_registry = MagicMock()
    mock_agent.subagents = {}

    with (
        patch("sage.cli.serve.JsonRpcServer", return_value=server),
        patch("sage.cli.serve.Agent.from_config", return_value=mock_agent),
        patch("sage.cli.serve.PersistentSessionManager", return_value=session_manager),
        patch("sage.cli.serve.MethodDispatcher", return_value=dispatcher),
        patch("sage.cli.serve.EventBridge", return_value=bridge),
    ):
        await _serve("AGENTS.md", verbose=False, yolo=True)

    mock_agent.tool_registry.set_permission_handler.assert_called_once()
    handler = mock_agent.tool_registry.set_permission_handler.call_args.args[0]
    assert isinstance(handler, AllowAllPermissionHandler)

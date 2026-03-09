from __future__ import annotations

import pytest

from sage.permissions.allow_all import AllowAllPermissionHandler
from sage.permissions.base import PermissionAction


@pytest.mark.asyncio
async def test_allow_all_permission_handler_approves_any_tool() -> None:
    handler = AllowAllPermissionHandler()

    decision = await handler.check("shell", {"command": "rm -rf /tmp/test"})

    assert decision.action == PermissionAction.ALLOW
    assert decision.reason == "YOLO mode enabled"

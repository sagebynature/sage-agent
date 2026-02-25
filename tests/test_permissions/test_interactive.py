"""Tests for InteractivePermissionHandler."""

from __future__ import annotations

from unittest.mock import AsyncMock


from sage.permissions.base import PermissionAction
from sage.permissions.interactive import InteractivePermissionHandler
from sage.permissions.policy import PermissionRule


class TestInteractivePermissionHandler:
    def _handler(
        self,
        callback: AsyncMock | None = None,
        rules: list[PermissionRule] | None = None,
        default: PermissionAction = PermissionAction.ASK,
    ) -> InteractivePermissionHandler:
        cb = callback or AsyncMock(return_value=True)
        return InteractivePermissionHandler(rules=rules or [], default=default, ask_callback=cb)

    async def test_allow_rule_does_not_call_callback(self) -> None:
        cb = AsyncMock(return_value=True)
        handler = self._handler(
            callback=cb,
            rules=[PermissionRule(tool="file_read", action=PermissionAction.ALLOW)],
        )
        decision = await handler.check("file_read", {"path": "/tmp"})
        assert decision.action == PermissionAction.ALLOW
        cb.assert_not_called()

    async def test_deny_rule_does_not_call_callback(self) -> None:
        cb = AsyncMock(return_value=True)
        handler = self._handler(
            callback=cb,
            rules=[PermissionRule(tool="web_fetch", action=PermissionAction.DENY)],
        )
        decision = await handler.check("web_fetch", {"url": "https://x.com"})
        assert decision.action == PermissionAction.DENY
        cb.assert_not_called()

    async def test_ask_calls_callback_approved(self) -> None:
        cb = AsyncMock(return_value=True)
        handler = self._handler(callback=cb, default=PermissionAction.ASK)
        decision = await handler.check("shell", {"command": "ls"})
        assert decision.action == PermissionAction.ALLOW
        cb.assert_awaited_once_with("shell", {"command": "ls"})

    async def test_ask_calls_callback_denied(self) -> None:
        cb = AsyncMock(return_value=False)
        handler = self._handler(callback=cb, default=PermissionAction.ASK)
        decision = await handler.check("shell", {"command": "rm -rf /"})
        assert decision.action == PermissionAction.DENY
        assert decision.reason is not None
        assert "denied" in decision.reason.lower()
        cb.assert_awaited_once()

    async def test_pattern_ask_calls_callback(self) -> None:
        cb = AsyncMock(return_value=True)
        handler = self._handler(
            callback=cb,
            rules=[
                PermissionRule(
                    tool="shell",
                    action=PermissionAction.DENY,
                    patterns={"git *": "allow", "*": "ask"},
                )
            ],
        )
        decision = await handler.check("shell", {"command": "curl foo"})
        assert decision.action == PermissionAction.ALLOW
        cb.assert_awaited_once()

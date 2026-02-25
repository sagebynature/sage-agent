"""Tests for permission base types."""

from __future__ import annotations


from sage.permissions.base import (
    PermissionAction,
    PermissionDecision,
    PermissionProtocol,
)
from sage.exceptions import PermissionError as SagePermissionError


class TestPermissionAction:
    def test_enum_values(self) -> None:
        assert PermissionAction.ALLOW.value == "allow"
        assert PermissionAction.DENY.value == "deny"
        assert PermissionAction.ASK.value == "ask"

    def test_enum_from_string(self) -> None:
        assert PermissionAction("allow") == PermissionAction.ALLOW
        assert PermissionAction("deny") == PermissionAction.DENY
        assert PermissionAction("ask") == PermissionAction.ASK


class TestPermissionDecision:
    def test_allow_decision(self) -> None:
        d = PermissionDecision(action=PermissionAction.ALLOW)
        assert d.action == PermissionAction.ALLOW
        assert d.reason is None

    def test_deny_with_reason(self) -> None:
        d = PermissionDecision(action=PermissionAction.DENY, reason="blocked by policy")
        assert d.reason == "blocked by policy"

    def test_destructive_flag_default(self) -> None:
        d = PermissionDecision(action=PermissionAction.ALLOW)
        assert d.destructive is False

    def test_destructive_flag_set(self) -> None:
        d = PermissionDecision(action=PermissionAction.ALLOW, destructive=True)
        assert d.destructive is True


class TestPermissionProtocol:
    async def test_protocol_runtime_checkable(self) -> None:
        class FakeHandler:
            async def check(self, tool_name: str, arguments: dict) -> PermissionDecision:
                return PermissionDecision(action=PermissionAction.ALLOW)

        handler = FakeHandler()
        assert isinstance(handler, PermissionProtocol)


class TestPermissionError:
    def test_inherits_from_sage_error(self) -> None:
        from sage.exceptions import SageError

        err = SagePermissionError("denied")
        assert isinstance(err, SageError)

    def test_message(self) -> None:
        err = SagePermissionError("Permission denied: shell")
        assert str(err) == "Permission denied: shell"

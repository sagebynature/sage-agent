"""Tests for PolicyPermissionHandler."""

from __future__ import annotations


from sage.permissions.base import PermissionAction
from sage.permissions.policy import PolicyPermissionHandler, PermissionRule


class TestPermissionRule:
    def test_simple_rule(self) -> None:
        rule = PermissionRule(tool="file_read", action=PermissionAction.ALLOW)
        assert rule.tool == "file_read"
        assert rule.action == PermissionAction.ALLOW
        assert rule.patterns is None
        assert rule.patterns is None

    def test_pattern_rule(self) -> None:
        rule = PermissionRule(
            tool="shell",
            action=PermissionAction.ASK,
            patterns={"git *": "allow", "rm *": "deny"},
        )
        assert rule.patterns == {"git *": "allow", "rm *": "deny"}


class TestPolicyPermissionHandler:
    def _handler(
        self,
        rules: list[PermissionRule] | None = None,
        default: PermissionAction = PermissionAction.ASK,
    ) -> PolicyPermissionHandler:
        return PolicyPermissionHandler(rules=rules or [], default=default)

    async def test_default_action_when_no_rules(self) -> None:
        handler = self._handler(default=PermissionAction.DENY)
        decision = await handler.check("unknown_tool", {})
        assert decision.action == PermissionAction.DENY

    async def test_simple_allow_rule(self) -> None:
        handler = self._handler(
            rules=[PermissionRule(tool="file_read", action=PermissionAction.ALLOW)]
        )
        decision = await handler.check("file_read", {"path": "/tmp/foo"})
        assert decision.action == PermissionAction.ALLOW

    async def test_simple_deny_rule(self) -> None:
        handler = self._handler(
            rules=[PermissionRule(tool="web_fetch", action=PermissionAction.DENY)]
        )
        decision = await handler.check("web_fetch", {"url": "https://evil.com"})
        assert decision.action == PermissionAction.DENY

    async def test_last_matching_rule_wins(self) -> None:
        handler = self._handler(
            rules=[
                PermissionRule(tool="shell", action=PermissionAction.DENY),
                PermissionRule(tool="shell", action=PermissionAction.ALLOW),
            ]
        )
        decision = await handler.check("shell", {"command": "ls"})
        assert decision.action == PermissionAction.ALLOW

    async def test_pattern_matching_allow(self) -> None:
        handler = self._handler(
            rules=[
                PermissionRule(
                    tool="shell",
                    action=PermissionAction.DENY,
                    patterns={"git *": "allow"},
                )
            ]
        )
        decision = await handler.check("shell", {"command": "git status"})
        assert decision.action == PermissionAction.ALLOW

    async def test_pattern_matching_deny(self) -> None:
        handler = self._handler(
            rules=[
                PermissionRule(
                    tool="shell",
                    action=PermissionAction.ALLOW,
                    patterns={"rm *": "deny"},
                )
            ]
        )
        decision = await handler.check("shell", {"command": "rm -rf /"})
        assert decision.action == PermissionAction.DENY

    async def test_pattern_wildcard_fallback(self) -> None:
        handler = self._handler(
            rules=[
                PermissionRule(
                    tool="shell",
                    action=PermissionAction.DENY,
                    patterns={"git *": "allow", "*": "ask"},
                )
            ]
        )
        decision = await handler.check("shell", {"command": "curl example.com"})
        assert decision.action == PermissionAction.ASK

    async def test_unmatched_tool_gets_default(self) -> None:
        handler = self._handler(
            rules=[PermissionRule(tool="file_read", action=PermissionAction.ALLOW)],
            default=PermissionAction.ASK,
        )
        decision = await handler.check("shell", {"command": "ls"})
        assert decision.action == PermissionAction.ASK

    async def test_no_command_arg_uses_rule_action(self) -> None:
        """When shell has patterns but arguments lack 'command', use rule's default action."""
        handler = self._handler(
            rules=[
                PermissionRule(
                    tool="shell",
                    action=PermissionAction.DENY,
                    patterns={"git *": "allow"},
                )
            ]
        )
        decision = await handler.check("shell", {})
        assert decision.action == PermissionAction.DENY

"""Tests for category-aware PolicyPermissionHandler."""

from __future__ import annotations

from sage.permissions.base import PermissionAction
from sage.permissions.policy import CategoryPermissionRule, PolicyPermissionHandler


class TestCategoryPermissionRule:
    def test_simple_rule(self) -> None:
        rule = CategoryPermissionRule(category="read", action=PermissionAction.ALLOW)
        assert rule.category == "read"
        assert rule.action == PermissionAction.ALLOW
        assert rule.patterns is None

    def test_pattern_rule(self) -> None:
        rule = CategoryPermissionRule(
            category="shell",
            action=PermissionAction.ASK,
            patterns={"git *": "allow", "rm *": "deny"},
        )
        assert rule.patterns == {"git *": "allow", "rm *": "deny"}


class TestPolicyPermissionHandler:
    def _handler(
        self,
        rules: list[CategoryPermissionRule] | None = None,
        default: PermissionAction = PermissionAction.ASK,
    ) -> PolicyPermissionHandler:
        return PolicyPermissionHandler(rules=rules or [], default=default)

    async def test_tool_in_category_allow(self) -> None:
        handler = self._handler(
            rules=[CategoryPermissionRule(category="shell", action=PermissionAction.ALLOW)]
        )
        decision = await handler.check("shell", {"command": "ls"})
        assert decision.action == PermissionAction.ALLOW

    async def test_tool_in_category_deny(self) -> None:
        handler = self._handler(
            rules=[CategoryPermissionRule(category="shell", action=PermissionAction.DENY)]
        )
        decision = await handler.check("shell", {"command": "ls"})
        assert decision.action == PermissionAction.DENY

    async def test_tool_not_in_any_category_is_allowed(self) -> None:
        # Tools with no category (e.g. MCP tools) always pass through — the user
        # explicitly configured the MCP server, so non-interactive ALLOW is correct.
        handler = self._handler(default=PermissionAction.DENY)
        decision = await handler.check("unknown_tool", {})
        assert decision.action == PermissionAction.ALLOW

    async def test_last_match_wins(self) -> None:
        handler = self._handler(
            rules=[
                CategoryPermissionRule(category="shell", action=PermissionAction.DENY),
                CategoryPermissionRule(category="shell", action=PermissionAction.ALLOW),
            ]
        )
        decision = await handler.check("shell", {"command": "ls"})
        assert decision.action == PermissionAction.ALLOW

    async def test_pattern_matching_shell(self) -> None:
        handler = self._handler(
            rules=[
                CategoryPermissionRule(
                    category="shell",
                    action=PermissionAction.DENY,
                    patterns={"git *": "allow"},
                )
            ]
        )
        decision = await handler.check("shell", {"command": "git status"})
        assert decision.action == PermissionAction.ALLOW

    async def test_pattern_matching_last_wins(self) -> None:
        handler = self._handler(
            rules=[
                CategoryPermissionRule(
                    category="shell",
                    action=PermissionAction.ASK,
                    patterns={"*": "deny", "git *": "allow"},
                )
            ]
        )
        decision = await handler.check("shell", {"command": "git status"})
        assert decision.action == PermissionAction.ALLOW

    async def test_pattern_no_match_uses_rule_action(self) -> None:
        handler = self._handler(
            rules=[
                CategoryPermissionRule(
                    category="shell",
                    action=PermissionAction.DENY,
                    patterns={"git *": "allow"},
                )
            ]
        )
        decision = await handler.check("shell", {"command": "ls"})
        assert decision.action == PermissionAction.DENY

    async def test_file_edit_arg_name_normalization(self) -> None:
        handler = self._handler(
            rules=[
                CategoryPermissionRule(
                    category="edit",
                    action=PermissionAction.ALLOW,
                    patterns={"*.py": "deny"},
                )
            ]
        )
        decision = await handler.check("file_edit", {"file_path": "src/main.py"})
        assert decision.action == PermissionAction.DENY

    async def test_empty_rules_uses_default(self) -> None:
        handler = self._handler(default=PermissionAction.ASK)
        decision = await handler.check("shell", {"command": "ls"})
        assert decision.action == PermissionAction.ASK

    async def test_read_category_tool(self) -> None:
        handler = self._handler(
            rules=[CategoryPermissionRule(category="read", action=PermissionAction.ALLOW)]
        )
        decision = await handler.check("file_read", {"path": "README.md"})
        assert decision.action == PermissionAction.ALLOW

    async def test_git_category_tool_resolved(self) -> None:
        handler = self._handler(
            rules=[CategoryPermissionRule(category="git", action=PermissionAction.ALLOW)]
        )
        decision = await handler.check("git_status", {})
        assert decision.action == PermissionAction.ALLOW

    async def test_git_snapshot_tool_in_git_category(self) -> None:
        handler = self._handler(
            rules=[CategoryPermissionRule(category="git", action=PermissionAction.DENY)]
        )
        decision = await handler.check("snapshot_create", {})
        assert decision.action == PermissionAction.DENY

    async def test_process_category_tool_resolved(self) -> None:
        handler = self._handler(
            rules=[CategoryPermissionRule(category="process", action=PermissionAction.DENY)]
        )
        decision = await handler.check("process_start", {"command": "python"})
        assert decision.action == PermissionAction.DENY

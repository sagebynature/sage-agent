"""Tests for git integration with Agent (tool registration)."""

from __future__ import annotations

from sage.config import AgentConfig, GitConfig, Permission
from sage.tools.registry import ToolRegistry


class TestGitToolRegistration:
    def test_git_tools_registered_when_permission_allows(self) -> None:
        registry = ToolRegistry()
        registry.register_from_permissions(Permission(git="allow"))
        names = {s.name for s in registry.get_schemas()}
        assert "git_status" in names
        assert "git_diff" in names
        assert "git_log" in names
        assert "git_commit" in names
        assert "git_branch" in names
        assert "git_undo" in names
        assert "git_worktree_create" in names
        assert "git_worktree_remove" in names

    def test_git_tools_not_registered_when_denied(self) -> None:
        registry = ToolRegistry()
        registry.register_from_permissions(Permission(git="deny"))
        names = {s.name for s in registry.get_schemas()}
        assert "git_status" not in names

    def test_snapshot_tools_registered_with_git_permission(self) -> None:
        registry = ToolRegistry()
        registry.register_from_permissions(Permission(git="allow"))
        names = {s.name for s in registry.get_schemas()}
        assert "snapshot_create" in names
        assert "snapshot_restore" in names
        assert "snapshot_list" in names


class TestGitConfigOnAgent:
    def test_git_config_on_agent_config(self) -> None:
        cfg = AgentConfig(
            name="test",
            model="gpt-4o",
            git=GitConfig(auto_snapshot=True, auto_commit_dirty=False),
        )
        assert cfg.git is not None
        assert cfg.git.auto_snapshot is True

    def test_git_config_default_none(self) -> None:
        cfg = AgentConfig(name="test", model="gpt-4o")
        assert cfg.git is None

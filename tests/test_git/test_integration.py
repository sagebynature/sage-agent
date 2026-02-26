"""End-to-end integration test for git tools."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from sage.exceptions import PermissionError as SagePermissionError
from sage.git.snapshot import GitSnapshot
from sage.git.tools import GitTools
from sage.permissions.base import PermissionAction, PermissionDecision
from sage.tools.registry import ToolRegistry


class TestGitIntegration:
    """End-to-end: register tools, execute via registry, verify results."""

    async def test_full_workflow_via_registry(self, git_repo: Path) -> None:
        git_tools = GitTools(repo_root=git_repo)
        snapshot = GitSnapshot(repo_path=str(git_repo))
        await git_tools.setup()
        await snapshot.setup()

        registry = ToolRegistry()
        registry.register(git_tools)
        registry.register(snapshot)

        # Verify all tools are registered.
        names = {s.name for s in registry.get_schemas()}
        assert "git_status" in names
        assert "git_commit" in names
        assert "git_undo" in names
        assert "git_branch" in names
        assert "git_worktree_create" in names
        assert "snapshot_create" in names

        # Execute status via registry.
        status = await registry.execute("git_status", {})
        assert isinstance(status, str)

        # Create a file, commit, check log.
        (git_repo / "feature.txt").write_text("new feature")
        commit_result = await registry.execute(
            "git_commit", {"message": "add feature", "files": ["feature.txt"]}
        )
        assert "add feature" in commit_result.lower() or "committed" in commit_result.lower()

        log_result = await registry.execute("git_log", {"count": 5})
        assert "add feature" in log_result.lower()

        # Undo the commit.
        undo_result = await registry.execute("git_undo", {})
        assert "undone" in undo_result.lower()

        # Snapshot workflow.
        (git_repo / "README.md").write_text("# Changed\n")
        snap_result = await registry.execute("snapshot_create", {"label": "test"})
        assert "sage:" in snap_result.lower() or "snapshot" in snap_result.lower()

    async def test_permission_controlled_execution(self, git_repo: Path) -> None:
        """Git tools respect permission handler."""
        git_tools = GitTools(repo_root=git_repo)
        await git_tools.setup()

        registry = ToolRegistry()
        registry.register(git_tools)

        handler = AsyncMock()
        handler.check = AsyncMock(
            return_value=PermissionDecision(action=PermissionAction.DENY, reason="blocked")
        )
        registry.set_permission_handler(handler)

        with pytest.raises(SagePermissionError, match="Permission denied"):
            await registry.execute("git_status", {})

    async def test_branch_and_worktree_flow(self, git_repo: Path) -> None:
        """Create a branch, create a worktree, remove it."""
        git_tools = GitTools(repo_root=git_repo)
        await git_tools.setup()

        registry = ToolRegistry()
        registry.register(git_tools)

        # Create a branch
        branch_result = await registry.execute("git_branch", {"name": "test-branch"})
        assert "test-branch" in branch_result

        # List branches
        list_result = await registry.execute("git_branch", {"list_branches": True})
        assert "test-branch" in list_result

        # Create worktree
        wt_result = await registry.execute("git_worktree_create", {"name": "test-wt"})
        assert "test-wt" in wt_result
        assert (git_repo / ".sage" / "worktrees" / "test-wt").exists()

        # Remove worktree
        rm_result = await registry.execute("git_worktree_remove", {"name": "test-wt"})
        assert "removed" in rm_result.lower()

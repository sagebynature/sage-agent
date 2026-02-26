"""Tests for GitTools (ToolBase)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sage.exceptions import ToolError
from sage.git.tools import GitTools


class TestGitToolsSetup:
    async def test_setup_in_git_repo(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()

    async def test_setup_outside_git_raises(self, tmp_path: Path) -> None:
        tools = GitTools(repo_root=tmp_path)
        with pytest.raises(ToolError, match="[Nn]ot a git repo"):
            await tools.setup()


class TestGitStatus:
    async def test_clean_status(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_status()
        assert "nothing to commit" in result.lower() or result.strip() == ""

    async def test_dirty_status(self, git_repo: Path) -> None:
        (git_repo / "new_file.txt").write_text("hello")
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_status()
        assert "new_file.txt" in result


class TestGitDiff:
    async def test_diff_no_changes(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_diff()
        assert result.strip() == "" or "no changes" in result.lower()

    async def test_diff_with_changes(self, git_repo: Path) -> None:
        (git_repo / "README.md").write_text("# Modified\n")
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_diff()
        assert "Modified" in result

    async def test_diff_staged(self, git_repo: Path) -> None:
        (git_repo / "README.md").write_text("# Staged\n")
        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(git_repo),
            "add",
            "README.md",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_diff(staged=True)
        assert "Staged" in result


class TestGitLog:
    async def test_log_shows_initial_commit(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_log()
        assert "initial" in result.lower()

    async def test_log_count(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_log(count=1)
        lines = [line for line in result.strip().split("\n") if line.strip()]
        assert len(lines) >= 1

    async def test_log_oneline_false(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_log(oneline=False)
        assert "commit" in result.lower() or "Author" in result


class TestGitCommit:
    async def test_commit_staged_files(self, git_repo: Path) -> None:
        (git_repo / "new.txt").write_text("content")
        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(git_repo),
            "add",
            "new.txt",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_commit(message="add new file")
        assert "add new file" in result.lower() or "committed" in result.lower()

    async def test_commit_specific_files(self, git_repo: Path) -> None:
        (git_repo / "a.txt").write_text("a")
        (git_repo / "b.txt").write_text("b")
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        await tools.git_commit(message="add a", files=["a.txt"])
        log_out, _ = await tools._git(["log", "--oneline", "-1"])
        assert "add a" in log_out.lower()

    async def test_commit_appends_co_author(self, git_repo: Path) -> None:
        (git_repo / "file.txt").write_text("data")
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        await tools.git_commit(message="test co-author", files=["file.txt"])
        log_out, _ = await tools._git(["log", "-1", "--format=%B"])
        assert "Co-authored-by: sage-agent" in log_out

    async def test_commit_tracks_hash(self, git_repo: Path) -> None:
        (git_repo / "file.txt").write_text("data")
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        await tools.git_commit(message="tracked commit", files=["file.txt"])
        assert len(tools._sage_commit_hashes) == 1

    async def test_commit_nothing_staged(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_commit(message="empty")
        assert "nothing" in result.lower() or "no changes" in result.lower()


class TestGitBranch:
    async def test_list_branches(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_branch(list_branches=True)
        assert "master" in result or "main" in result

    async def test_create_branch(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_branch(name="feature-test")
        assert "feature-test" in result
        listing = await tools.git_branch(list_branches=True)
        assert "feature-test" in listing

    async def test_create_branch_no_name_lists(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_branch()
        # With no name and list_branches=False (default), should list branches
        assert isinstance(result, str)
        assert "master" in result or "main" in result


class TestGitWorktree:
    async def test_create_worktree(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_worktree_create(name="test-wt")
        assert "test-wt" in result
        wt_path = git_repo / ".sage" / "worktrees" / "test-wt"
        assert wt_path.exists()

    async def test_create_worktree_with_branch(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_worktree_create(name="branched-wt", branch="feat-branch")
        assert "branched-wt" in result
        wt_path = git_repo / ".sage" / "worktrees" / "branched-wt"
        assert wt_path.exists()

    async def test_remove_worktree(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        await tools.git_worktree_create(name="to-remove")
        result = await tools.git_worktree_remove(name="to-remove")
        assert "removed" in result.lower()

    async def test_remove_nonexistent_worktree(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_worktree_remove(name="nope")
        assert "not found" in result.lower()

    async def test_create_worktree_path_traversal_rejected(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        with pytest.raises(ToolError, match="Invalid worktree name"):
            await tools.git_worktree_create(name="../../../tmp/evil")

    async def test_remove_worktree_path_traversal_rejected(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        with pytest.raises(ToolError, match="Invalid worktree name"):
            await tools.git_worktree_remove(name="../../../tmp/evil")

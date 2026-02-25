"""Tests for git tools."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from sage.exceptions import ToolError
from sage.tools.git_tools import (
    _git,
    git_status,
    git_diff,
    git_commit,
    git_log,
    git_checkout,
)


async def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "init",
        cwd=str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    # Configure git user for commits
    for cmd in [
        ["git", "config", "user.email", "test@test.com"],
        ["git", "config", "user.name", "Test"],
    ]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    # Initial commit
    (path / "README.md").write_text("# Test")
    proc = await asyncio.create_subprocess_exec(
        "git",
        "add",
        ".",
        cwd=str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    proc = await asyncio.create_subprocess_exec(
        "git",
        "commit",
        "-m",
        "initial",
        cwd=str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


class TestGitStatus:
    async def test_clean_repo(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        result = await git_status(repo_path=str(tmp_path))
        assert "nothing to commit" in result.lower() or "clean" in result.lower()

    async def test_dirty_repo(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "new.txt").write_text("change")
        result = await git_status(repo_path=str(tmp_path))
        assert "new.txt" in result


class TestGitDiff:
    async def test_unstaged_diff(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("# Changed")
        result = await git_diff(repo_path=str(tmp_path))
        assert "Changed" in result

    async def test_staged_diff(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("# Staged")
        proc = await asyncio.create_subprocess_exec(
            "git",
            "add",
            ".",
            cwd=str(tmp_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        result = await git_diff(staged=True, repo_path=str(tmp_path))
        assert "Staged" in result


class TestGitCommit:
    async def test_commit_staged_changes(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "new.txt").write_text("content")
        proc = await asyncio.create_subprocess_exec(
            "git",
            "add",
            ".",
            cwd=str(tmp_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        result = await git_commit(message="add new file", repo_path=str(tmp_path))
        assert "add new file" in result or "1 file" in result.lower() or "create" in result.lower()


class TestGitLog:
    async def test_shows_initial_commit(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        result = await git_log(count=5, repo_path=str(tmp_path))
        assert "initial" in result


class TestGitCheckout:
    async def test_create_and_switch_branch(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        result = await git_checkout(branch="feature", create=True, repo_path=str(tmp_path))
        assert "feature" in result.lower() or "switched" in result.lower()

        # Verify we're on the new branch
        status = await git_status(repo_path=str(tmp_path))
        assert "feature" in status


class TestGitErrorDetection:
    async def test_fatal_error_detected(self) -> None:
        """git commands with 'fatal:' in stderr should raise ToolError."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"fatal: not a git repository"))
        mock_proc.returncode = 128

        with patch("sage.tools.git_tools.asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(ToolError, match="git .* failed"):
                await _git(["status"])

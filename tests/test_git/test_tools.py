"""Tests for GitTools (ToolBase)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sage.exceptions import ToolError
from sage.git.tools import GitTools


async def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    for cmd in [
        ["git", "init"],
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
    (path / "README.md").write_text("# Test\n")
    for cmd in [["git", "add", "."], ["git", "commit", "-m", "initial"]]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()


class TestGitToolsSetup:
    async def test_setup_in_git_repo(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()

    async def test_setup_outside_git_raises(self, tmp_path: Path) -> None:
        tools = GitTools(repo_root=tmp_path)
        with pytest.raises(ToolError, match="[Nn]ot a git repo"):
            await tools.setup()


class TestGitStatus:
    async def test_clean_status(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_status()
        assert "nothing to commit" in result.lower() or result.strip() == ""

    async def test_dirty_status(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "new_file.txt").write_text("hello")
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_status()
        assert "new_file.txt" in result


class TestGitDiff:
    async def test_diff_no_changes(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_diff()
        assert result.strip() == "" or "no changes" in result.lower()

    async def test_diff_with_changes(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("# Modified\n")
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_diff()
        assert "Modified" in result

    async def test_diff_staged(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("# Staged\n")
        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(tmp_path),
            "add",
            "README.md",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_diff(staged=True)
        assert "Staged" in result


class TestGitLog:
    async def test_log_shows_initial_commit(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_log()
        assert "initial" in result.lower()

    async def test_log_count(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_log(count=1)
        lines = [line for line in result.strip().split("\n") if line.strip()]
        assert len(lines) >= 1

    async def test_log_oneline_false(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_log(oneline=False)
        assert "commit" in result.lower() or "Author" in result


class TestGitCommit:
    async def test_commit_staged_files(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "new.txt").write_text("content")
        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(tmp_path),
            "add",
            "new.txt",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_commit(message="add new file")
        assert "add new file" in result.lower() or "committed" in result.lower()

    async def test_commit_specific_files(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        await tools.git_commit(message="add a", files=["a.txt"])
        log_out, _ = await tools._git(["log", "--oneline", "-1"])
        assert "add a" in log_out.lower()

    async def test_commit_appends_co_author(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "file.txt").write_text("data")
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        await tools.git_commit(message="test co-author", files=["file.txt"])
        log_out, _ = await tools._git(["log", "-1", "--format=%B"])
        assert "Co-authored-by: sage-agent" in log_out

    async def test_commit_tracks_hash(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        (tmp_path / "file.txt").write_text("data")
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        await tools.git_commit(message="tracked commit", files=["file.txt"])
        assert len(tools._sage_commit_hashes) == 1

    async def test_commit_nothing_staged(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_commit(message="empty")
        assert "nothing" in result.lower() or "no changes" in result.lower()

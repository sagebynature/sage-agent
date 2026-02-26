"""Tests for git_undo safety checks."""

from __future__ import annotations

import asyncio
from pathlib import Path


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


class TestGitUndo:
    async def test_undo_sage_commit(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        (tmp_path / "file.txt").write_text("data")
        await tools.git_commit(message="to undo", files=["file.txt"])
        assert len(tools._sage_commit_hashes) == 1
        result = await tools.git_undo()
        assert "undone" in result.lower() or "reset" in result.lower()
        assert (tmp_path / "file.txt").exists()

    async def test_undo_non_sage_commit_rejected(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        result = await tools.git_undo()
        assert "no sage" in result.lower() or "cannot undo" in result.lower()

    async def test_undo_clears_hash_tracking(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        (tmp_path / "file.txt").write_text("data")
        await tools.git_commit(message="to undo", files=["file.txt"])
        assert len(tools._sage_commit_hashes) == 1
        await tools.git_undo()
        assert len(tools._sage_commit_hashes) == 0

    async def test_undo_pushed_commit_rejected(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        remote_path = tmp_path.parent / "remote.git"
        for cmd in [["git", "init", "--bare", str(remote_path)]]:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        for cmd in [
            ["git", "-C", str(tmp_path), "remote", "add", "origin", str(remote_path)],
            ["git", "-C", str(tmp_path), "push", "-u", "origin", "master"],
        ]:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        tools = GitTools(repo_root=tmp_path)
        await tools.setup()
        (tmp_path / "file.txt").write_text("data")
        await tools.git_commit(message="will push", files=["file.txt"])
        await tools._git(["push", "origin", "HEAD"])
        result = await tools.git_undo()
        assert "pushed" in result.lower() or "cannot undo" in result.lower()

"""Tests for git_undo safety checks."""

from __future__ import annotations

import asyncio
from pathlib import Path

from sage.git.tools import GitTools


class TestGitUndo:
    async def test_undo_sage_commit(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        (git_repo / "file.txt").write_text("data")
        await tools.git_commit(message="to undo", files=["file.txt"])
        assert len(tools._sage_commit_hashes) == 1
        result = await tools.git_undo()
        assert "undone" in result.lower() or "reset" in result.lower()
        assert (git_repo / "file.txt").exists()

    async def test_undo_non_sage_commit_rejected(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        result = await tools.git_undo()
        assert "no sage" in result.lower() or "cannot undo" in result.lower()

    async def test_undo_clears_hash_tracking(self, git_repo: Path) -> None:
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        (git_repo / "file.txt").write_text("data")
        await tools.git_commit(message="to undo", files=["file.txt"])
        assert len(tools._sage_commit_hashes) == 1
        await tools.git_undo()
        assert len(tools._sage_commit_hashes) == 0

    async def test_undo_pushed_commit_rejected(self, git_repo: Path) -> None:
        remote_path = git_repo.parent / "remote.git"
        for cmd in [["git", "init", "--bare", str(remote_path)]]:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        for cmd in [
            ["git", "-C", str(git_repo), "remote", "add", "origin", str(remote_path)],
            ["git", "-C", str(git_repo), "push", "-u", "origin", "master"],
        ]:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        tools = GitTools(repo_root=git_repo)
        await tools.setup()
        (git_repo / "file.txt").write_text("data")
        await tools.git_commit(message="will push", files=["file.txt"])
        await tools._git(["push", "origin", "HEAD"])
        result = await tools.git_undo()
        assert "pushed" in result.lower() or "cannot undo" in result.lower()

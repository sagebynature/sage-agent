"""Tests for GitSnapshot ToolBase."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sage.exceptions import ToolError
from sage.git.snapshot import GitSnapshot


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


class TestGitSnapshot:
    async def test_setup_in_git_repo(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        snap = GitSnapshot(repo_path=str(tmp_path))
        await snap.setup()  # Should not raise

    async def test_setup_outside_git_raises(self, tmp_path: Path) -> None:
        snap = GitSnapshot(repo_path=str(tmp_path))
        with pytest.raises(ToolError, match="[Nn]ot a git repo"):
            await snap.setup()

    async def test_create_and_list_snapshot(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        snap = GitSnapshot(repo_path=str(tmp_path))
        await snap.setup()

        # Make a change so stash has something to capture.
        (tmp_path / "README.md").write_text("# Changed\n")

        result = await snap.snapshot_create(label="test-snap")
        assert "snapshot" in result.lower() or "sage:" in result.lower()

        listing = await snap.snapshot_list()
        assert "sage:" in listing

    async def test_create_snapshot_no_changes(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        snap = GitSnapshot(repo_path=str(tmp_path))
        await snap.setup()

        result = await snap.snapshot_create(label="empty")
        assert "no changes" in result.lower() or "nothing" in result.lower()

    async def test_restore_snapshot(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        snap = GitSnapshot(repo_path=str(tmp_path))
        await snap.setup()

        # Change file, snapshot, change again, restore.
        readme = tmp_path / "README.md"
        readme.write_text("# Version A\n")
        await snap.snapshot_create(label="version-a")

        readme.write_text("# Version B\n")
        await snap.snapshot_restore()

        assert readme.read_text() == "# Version A\n"

    async def test_restore_preserves_uncommitted_changes_as_backup(self, tmp_path: Path) -> None:
        """Restoring a snapshot should stash uncommitted changes first."""
        await _init_git_repo(tmp_path)
        snap = GitSnapshot(repo_path=str(tmp_path))
        await snap.setup()

        readme = tmp_path / "README.md"

        # Create snapshot of version A.
        readme.write_text("# Version A\n")
        await snap.snapshot_create(label="version-a")

        # Make uncommitted changes (version B).
        readme.write_text("# Version B\n")

        # Restore version A — uncommitted version B should be stashed.
        await snap.snapshot_restore()

        # The restore created a backup stash entry.
        listing, _ = await snap._git(["stash", "list"])
        assert "sage:pre-restore-backup" in listing

    async def test_snapshot_list_empty(self, tmp_path: Path) -> None:
        await _init_git_repo(tmp_path)
        snap = GitSnapshot(repo_path=str(tmp_path))
        await snap.setup()

        listing = await snap.snapshot_list()
        assert "no snapshot" in listing.lower() or listing.strip() == ""

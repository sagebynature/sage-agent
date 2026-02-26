"""Tests for GitSnapshot ToolBase."""

from __future__ import annotations

from pathlib import Path

import pytest

from sage.exceptions import ToolError
from sage.git.snapshot import GitSnapshot


class TestGitSnapshot:
    async def test_setup_in_git_repo(self, git_repo: Path) -> None:
        snap = GitSnapshot(repo_path=str(git_repo))
        await snap.setup()  # Should not raise

    async def test_setup_outside_git_raises(self, tmp_path: Path) -> None:
        snap = GitSnapshot(repo_path=str(tmp_path))
        with pytest.raises(ToolError, match="[Nn]ot a git repo"):
            await snap.setup()

    async def test_create_and_list_snapshot(self, git_repo: Path) -> None:
        snap = GitSnapshot(repo_path=str(git_repo))
        await snap.setup()

        # Make a change so stash has something to capture.
        (git_repo / "README.md").write_text("# Changed\n")

        result = await snap.snapshot_create(label="test-snap")
        assert "snapshot" in result.lower() or "sage:" in result.lower()

        listing = await snap.snapshot_list()
        assert "sage:" in listing

    async def test_create_snapshot_no_changes(self, git_repo: Path) -> None:
        snap = GitSnapshot(repo_path=str(git_repo))
        await snap.setup()

        result = await snap.snapshot_create(label="empty")
        assert "no changes" in result.lower() or "nothing" in result.lower()

    async def test_restore_snapshot(self, git_repo: Path) -> None:
        snap = GitSnapshot(repo_path=str(git_repo))
        await snap.setup()

        # Change file, snapshot, change again, restore.
        readme = git_repo / "README.md"
        readme.write_text("# Version A\n")
        await snap.snapshot_create(label="version-a")

        readme.write_text("# Version B\n")
        await snap.snapshot_restore()

        assert readme.read_text() == "# Version A\n"

    async def test_restore_preserves_uncommitted_changes_as_backup(self, git_repo: Path) -> None:
        """Restoring a snapshot should stash uncommitted changes first."""
        snap = GitSnapshot(repo_path=str(git_repo))
        await snap.setup()

        readme = git_repo / "README.md"

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

    async def test_snapshot_list_empty(self, git_repo: Path) -> None:
        snap = GitSnapshot(repo_path=str(git_repo))
        await snap.setup()

        listing = await snap.snapshot_list()
        assert "no snapshot" in listing.lower() or listing.strip() == ""

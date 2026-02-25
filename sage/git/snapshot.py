"""Git-based snapshot/undo for destructive operations."""

from __future__ import annotations

import asyncio
import logging
import time

from sage.exceptions import ToolError
from sage.tools.base import ToolBase
from sage.tools.decorator import tool

logger = logging.getLogger(__name__)


class GitSnapshot(ToolBase):
    """Git-based snapshot/undo for destructive operations.

    Uses git stash plumbing commands with a ``sage:`` prefix to avoid
    interfering with the user's stash, branches, or staging area.
    """

    def __init__(self, repo_path: str = ".") -> None:
        self.repo_path = repo_path
        super().__init__()

    async def _git(self, args: list[str]) -> tuple[str, int]:
        """Run a git command and return (output, returncode)."""
        cmd = ["git", "-C", self.repo_path] + args
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode(errors="replace").strip()
        err = stderr.decode(errors="replace").strip()
        combined = output or err
        return combined, proc.returncode or 0

    async def setup(self) -> None:
        """Verify we're inside a git repository."""
        output, rc = await self._git(["rev-parse", "--is-inside-work-tree"])
        if rc != 0 or output.strip() != "true":
            raise ToolError(f"Not a git repo: {self.repo_path}")

    async def teardown(self) -> None:
        """No-op — snapshots are kept for safety."""

    @tool
    async def snapshot_create(self, label: str = "") -> str:
        """Create a snapshot of the current working tree state."""
        # git stash create produces a commit object without modifying workdir.
        output, rc = await self._git(["stash", "create"])
        if rc != 0 or not output.strip():
            return "No changes to snapshot."

        stash_ref = output.strip()
        ts = int(time.time())
        tag = f"sage:{label}:{ts}" if label else f"sage:snapshot:{ts}"

        # Store the stash ref with our label.
        _, store_rc = await self._git(["stash", "store", "-m", tag, stash_ref])
        if store_rc != 0:
            raise ToolError(f"Failed to store snapshot: {stash_ref}")

        logger.info("Created snapshot: %s -> %s", tag, stash_ref[:8])
        return f"Snapshot created: {tag}"

    @tool
    async def snapshot_restore(self, snapshot_id: str | None = None) -> str:
        """Restore working tree to a previous snapshot.

        If snapshot_id is not provided, restores the most recent sage snapshot.
        """
        # Find the stash index to restore.
        listing, _ = await self._git(["stash", "list"])
        if not listing:
            return "No snapshots available."

        lines = listing.strip().split("\n")
        target_idx: int | None = None

        for line in lines:
            if "sage:" not in line:
                continue
            if snapshot_id and snapshot_id not in line:
                continue
            # Extract stash index: "stash@{0}: ..."
            idx_str = line.split(":")[0].strip()  # "stash@{0}"
            try:
                idx = int(idx_str.split("{")[1].rstrip("}"))
                target_idx = idx
                break
            except (IndexError, ValueError):
                continue

        if target_idx is None:
            return "No matching sage snapshot found."

        # Safety: stash any uncommitted changes before the destructive checkout.
        stash_out, _ = await self._git(["stash", "create"])
        if stash_out.strip():
            await self._git(["stash", "store", "-m", "sage:pre-restore-backup", stash_out.strip()])
            logger.warning("Stashed uncommitted changes before restore: %s", stash_out.strip()[:8])
            # The new stash entry shifts all existing indices by 1.
            target_idx += 1

        # Reset working tree to HEAD before applying to avoid conflicts.
        await self._git(["checkout", "--", "."])

        # Apply (not pop) — preserve the snapshot.
        _, rc = await self._git(["stash", "apply", f"stash@{{{target_idx}}}"])
        if rc != 0:
            raise ToolError(f"Failed to restore snapshot stash@{{{target_idx}}}")

        logger.info("Restored snapshot stash@{%d}", target_idx)
        return f"Restored snapshot stash@{{{target_idx}}}"

    @tool
    async def snapshot_list(self) -> str:
        """List available sage snapshots."""
        listing, _ = await self._git(["stash", "list"])
        if not listing:
            return "No snapshots available."

        sage_entries = [line for line in listing.split("\n") if "sage:" in line]
        if not sage_entries:
            return "No snapshots available."

        return "\n".join(sage_entries)

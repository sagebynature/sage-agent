"""First-class git integration tools."""

from __future__ import annotations

import logging
from pathlib import Path

from sage.exceptions import ToolError
from sage.git.utils import run_git
from sage.tools.base import ToolBase
from sage.tools.decorator import tool

logger = logging.getLogger(__name__)

_CO_AUTHOR_TRAILER = "Co-authored-by: sage-agent <noreply@sagebynature.com>"


class GitTools(ToolBase):
    """First-class git integration tools.

    Provides ``@tool``-decorated methods for common read-only git operations
    (status, diff, log).  Destructive operations such as commit, branch
    management, and worktree handling are intentionally deferred to later tasks.

    Args:
        repo_root: Path to the repository root.  Defaults to ``Path.cwd()``.

    Example::

        tools = GitTools(repo_root=Path("/path/to/repo"))
        await tools.setup()
        status = await tools.git_status()
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root = str(repo_root or Path.cwd())
        self._sage_commit_hashes: set[str] = set()
        super().__init__()

    async def _git(self, args: list[str]) -> tuple[str, int]:
        """Delegate to the shared ``run_git`` helper."""
        return await run_git(args, repo_path=self._repo_root)

    async def setup(self) -> None:
        """Verify we're inside a git repository.

        Raises:
            ToolError: If *repo_root* is not inside a git working tree.
        """
        output, rc = await self._git(["rev-parse", "--is-inside-work-tree"])
        if rc != 0 or output.strip() != "true":
            raise ToolError(f"Not a git repo: {self._repo_root}")

    async def teardown(self) -> None:
        """No-op — no resources to release."""

    @tool
    async def git_status(self) -> str:
        """Show working tree status (staged, unstaged, untracked files).

        Returns the full output of ``git status``, which lists files that have
        been modified, staged, or are untracked relative to HEAD.

        Returns:
            Human-readable status output from git.

        Raises:
            ToolError: If the underlying git command fails.
        """
        logger.debug("git_status")
        output, rc = await self._git(["status"])
        if rc != 0:
            raise ToolError(f"git status failed: {output}")
        return output

    @tool
    async def git_diff(self, ref: str = "HEAD", staged: bool = False) -> str:
        """Show diff of changes. Use staged=True for staged changes only.

        By default shows the diff of unstaged working-tree changes against
        *ref*.  When *staged* is ``True`` the ``--staged`` flag is passed and
        *ref* is ignored, returning only changes that have been added to the
        index.

        Args:
            ref: Git ref to diff against (default ``"HEAD"``).  Ignored when
                *staged* is ``True``.
            staged: If ``True``, show staged (index) changes instead of
                unstaged working-tree changes.

        Returns:
            Unified diff output, or ``"No changes."`` when the diff is empty.

        Raises:
            ToolError: If the underlying git command fails.
        """
        logger.debug("git_diff: ref=%s, staged=%s", ref, staged)
        args = ["diff"]
        if staged:
            args.append("--staged")
        else:
            args.append(ref)
        output, rc = await self._git(args)
        if rc != 0:
            raise ToolError(f"git diff failed: {output}")
        return output if output else "No changes."

    @tool
    async def git_log(self, count: int = 10, oneline: bool = True) -> str:
        """Show recent commit history.

        Args:
            count: Maximum number of commits to show (default ``10``).
            oneline: If ``True`` (default), use ``--oneline`` format for a
                compact single-line-per-commit view.  Set to ``False`` for the
                full multi-line commit format including author and date.

        Returns:
            Formatted commit log output from git.

        Raises:
            ToolError: If the underlying git command fails.
        """
        logger.debug("git_log: count=%d, oneline=%s", count, oneline)
        args = ["log", f"-{count}"]
        if oneline:
            args.append("--oneline")
        output, rc = await self._git(args)
        if rc != 0:
            raise ToolError(f"git log failed: {output}")
        return output

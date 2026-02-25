"""Git tools for version control operations."""

from __future__ import annotations

import asyncio
import logging

from sage.exceptions import ToolError
from sage.tools.decorator import tool

logger = logging.getLogger(__name__)


async def _git(args: list[str], repo_path: str = ".") -> str:
    """Run a git command and return output."""
    cmd = ["git", "-C", repo_path] + args
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    output = stdout.decode(errors="replace").strip()
    err = stderr.decode(errors="replace").strip()

    if proc.returncode != 0 and proc.returncode is not None:
        # Some git commands write to stderr normally (e.g. git checkout)
        if err and ("error" in err.lower() or "fatal" in err.lower()):
            raise ToolError(f"git {args[0]} failed: {err}")

    # Combine stdout and informational stderr
    if err and not output:
        return err
    if err:
        return f"{output}\n{err}"
    return output


@tool
async def git_status(repo_path: str = ".") -> str:
    """Show working tree status."""
    logger.debug("git_status: %s", repo_path)
    return await _git(["status"], repo_path)


@tool
async def git_diff(staged: bool = False, target: str | None = None, repo_path: str = ".") -> str:
    """Show changes. Use staged=True for staged changes, target for diff against a branch."""
    logger.debug("git_diff: staged=%s target=%s", staged, target)
    args = ["diff"]
    if staged:
        args.append("--cached")
    if target:
        args.append(target)
    return await _git(args, repo_path)


@tool
async def git_commit(message: str, files: list[str] | None = None, repo_path: str = ".") -> str:
    """Create a git commit. If files not specified, commits all staged changes."""
    logger.debug("git_commit: %s", message[:80])
    if files:
        await _git(["add"] + files, repo_path)
    result = await _git(["commit", "-m", message], repo_path)
    return result


@tool
async def git_log(count: int = 10, oneline: bool = True, repo_path: str = ".") -> str:
    """Show recent commit history."""
    logger.debug("git_log: count=%d", count)
    args = ["log", f"-{count}"]
    if oneline:
        args.append("--oneline")
    return await _git(args, repo_path)


@tool
async def git_checkout(branch: str, create: bool = False, repo_path: str = ".") -> str:
    """Switch or create branches."""
    logger.debug("git_checkout: branch=%s create=%s", branch, create)
    args = ["checkout"]
    if create:
        args.append("-b")
    args.append(branch)
    return await _git(args, repo_path)


@tool
async def git_pr_create(title: str, body: str, base: str = "main", repo_path: str = ".") -> str:
    """Create a GitHub pull request using gh CLI. Requires gh to be authenticated."""
    logger.debug("git_pr_create: %s", title[:80])
    cmd = [
        "gh",
        "pr",
        "create",
        "--title",
        title,
        "--body",
        body,
        "--base",
        base,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=repo_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        raise ToolError(f"gh pr create failed: {err}")

    return stdout.decode(errors="replace").strip()

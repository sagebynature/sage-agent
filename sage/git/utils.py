"""Shared async git subprocess helper."""

from __future__ import annotations

import asyncio


async def run_git(args: list[str], repo_path: str = ".") -> tuple[str, int]:
    """Run a git command in *repo_path* and return ``(output, returncode)``.

    stdout and stderr are merged: if stdout is non-empty it is returned as-is,
    otherwise stderr is returned.  This matches the behaviour expected by callers
    that want to surface both normal output and error messages through a single
    string return value.

    Args:
        args: git sub-command and arguments, e.g. ``["status"]``.
        repo_path: path to the repository root (passed via ``git -C``).

    Returns:
        A ``(output, returncode)`` tuple where *output* is the decoded,
        stripped combined output and *returncode* is the process exit code.

    Example::

        output, rc = await run_git(["status"], repo_path="/path/to/repo")
    """
    cmd = ["git", "-C", repo_path] + args
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

"""File manipulation tools: edit, glob, grep."""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import os
import re
import tempfile
from pathlib import Path

from sage.exceptions import ToolError
from sage.tools.decorator import tool

logger = logging.getLogger(__name__)


def _validate_path(path: str, allowed_dir: Path | None = None) -> Path:
    """Validate that a path resolves within the allowed directory.

    Raises ToolError if the resolved path is outside the allowed directory.
    Defaults to CWD if no allowed_dir is specified.
    """
    resolved = Path(path).resolve()
    base = (allowed_dir or Path.cwd()).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ToolError(f"Access denied: {path} is outside allowed directory ({base})")
    return resolved


@tool
async def file_edit(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Replace exact string occurrences in a file.

    old_string must match exactly (including whitespace/indentation).
    Fails if old_string is not found or is ambiguous (multiple matches
    when replace_all is False).
    """
    logger.debug("file_edit: %s", path)
    file_path = _validate_path(path)
    if not file_path.is_file():
        raise ToolError(f"File not found: {path}")

    content = file_path.read_text(encoding="utf-8")
    count = content.count(old_string)

    if count == 0:
        raise ToolError(f"String not found in {path}: {old_string!r}")

    if not replace_all and count > 1:
        raise ToolError(
            f"String is ambiguous in {path}: found {count} matches. "
            "Use replace_all=True to replace all, or provide more context to make "
            "the match unique."
        )

    if replace_all:
        new_content = content.replace(old_string, new_string)
    else:
        new_content = content.replace(old_string, new_string, 1)

    # Preserve original file permissions.
    original_mode = file_path.stat().st_mode

    # Atomic write: write to temp file, then rename.
    dir_path = file_path.parent
    fd, tmp_path_str = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
    try:
        os.write(fd, new_content.encode("utf-8"))
        os.close(fd)
        os.chmod(tmp_path_str, original_mode)
        os.replace(tmp_path_str, str(file_path))
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        if os.path.exists(tmp_path_str):
            os.unlink(tmp_path_str)
        raise

    replaced = count if replace_all else 1
    return f"Made {replaced} replacement(s) in {path}"


def _find_fd_binary() -> str | None:
    """Find the fd binary (fd or fdfind depending on platform)."""
    import shutil

    for name in ("fd", "fdfind"):
        if shutil.which(name):
            return name
    return None


@tool
async def glob_find(pattern: str, path: str = ".", max_results: int = 200) -> str:
    """Find files matching a glob pattern.

    Uses fd if available, otherwise falls back to Python pathlib.glob.
    Examples: '*.py', '**/*.ts', '*.md'
    Returns file paths one per line. Max 200 results.
    """
    logger.debug("glob_find: pattern=%s path=%s", pattern, path)
    _validate_path(path)

    fd_bin = _find_fd_binary()
    if fd_bin is not None:
        cmd = [fd_bin, "--glob", pattern, path, "--max-results", str(max_results)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode is not None and proc.returncode != 0:
            err = stderr.decode(errors="replace").strip()
            if err:
                raise ToolError(f"glob_find failed: {err}")
        output = stdout.decode(errors="replace").strip()
        if not output:
            return "No matches found."
        return output

    # Fallback: Python pathlib.glob.
    base = Path(path)
    if not base.exists():
        return "No matches found."
    # Use rglob for recursive patterns, glob for simple ones.
    use_pattern = f"**/{pattern}" if "**" not in pattern else pattern
    matches = sorted(base.glob(use_pattern))[:max_results]
    if not matches:
        return "No matches found."
    return "\n".join(str(m) for m in matches)


@tool
async def grep_search(
    pattern: str,
    path: str = ".",
    glob: str | None = None,
    context_lines: int = 0,
    max_results: int = 50,
) -> str:
    """Search file contents for a regex pattern using ripgrep.

    Falls back to a pure-Python implementation when ``rg`` is not installed.

    Args:
        pattern: Regex pattern to search for.
        path: Directory or file to search in.
        glob: Filter to specific file types (e.g. '*.py').
        context_lines: Lines of context around each match.
        max_results: Maximum number of matching lines to return.
    """
    logger.debug("grep_search: pattern=%s path=%s", pattern, path)
    _validate_path(path)

    try:
        return await _grep_rg(pattern, path, glob, context_lines, max_results)
    except FileNotFoundError:
        logger.debug("ripgrep (rg) not found, using Python fallback")
        return await _grep_python(pattern, path, glob, max_results)


async def _grep_rg(
    pattern: str,
    path: str,
    glob: str | None,
    context_lines: int,
    max_results: int,
) -> str:
    """Run ripgrep and return output."""
    cmd = ["rg", "--max-count", str(max_results), "-n"]
    if glob:
        cmd.extend(["--glob", glob])
    if context_lines > 0:
        cmd.extend(["-C", str(context_lines)])
    cmd.extend(["--", pattern, path])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    # Exit code 0 = matches found, 1 = no matches, 2+ = error.
    if proc.returncode is not None and proc.returncode >= 2:
        err = stderr.decode(errors="replace").strip()
        raise ToolError(
            f"grep_search failed: {err or f'ripgrep error (exit code {proc.returncode})'}"
        )

    output = stdout.decode(errors="replace").strip()
    if not output:
        return "No matches found."
    return output


async def _grep_python(
    pattern: str,
    path: str,
    glob_pattern: str | None,
    max_results: int,
) -> str:
    """Pure-Python fallback grep when ripgrep is unavailable."""
    regex = re.compile(pattern)
    target = Path(path)
    matches: list[str] = []

    files: list[Path] = []
    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = sorted(target.rglob("*"))
    else:
        return "No matches found."

    for fp in files:
        if not fp.is_file():
            continue
        if glob_pattern and not fnmatch.fnmatch(fp.name, glob_pattern):
            continue
        try:
            lines = fp.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            if regex.search(line):
                matches.append(f"{fp}:{lineno}:{line}")
                if len(matches) >= max_results:
                    break
        if len(matches) >= max_results:
            break

    if not matches:
        return "No matches found."
    return "\n".join(matches)

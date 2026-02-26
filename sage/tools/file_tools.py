"""File manipulation tools: edit."""

from __future__ import annotations

import logging
import os
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

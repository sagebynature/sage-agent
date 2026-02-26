"""Tests for git-specific dangerous pattern detection in the shell tool."""

from __future__ import annotations

import pytest

from sage.exceptions import ToolError
from sage.tools.builtins import shell


class TestGitDangerousPatterns:
    """Verify git-specific dangerous commands are rejected by the shell tool."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "git push origin main --force",
            "git push -f origin feature",
            "git reset --hard HEAD~3",
            "git clean -fd",
            "git clean -f",
            "git checkout .",
            "git branch -D feature-branch",
            "git rebase main",
            "git push origin main",
            "git push origin master",
        ],
    )
    async def test_dangerous_git_command_rejected(self, cmd: str) -> None:
        with pytest.raises(ToolError, match="Command rejected"):
            await shell(command=cmd)

    @pytest.mark.parametrize(
        "cmd",
        [
            "git status",
            "git diff",
            "git log --oneline -10",
            "git branch --list",
            "git add README.md",
            "git commit -m 'fix: typo'",
            "git push origin feature-branch",
            "git stash list",
            "git diff --staged",
            "git checkout -b new-branch",
        ],
    )
    async def test_safe_git_command_allowed(self, cmd: str) -> None:
        try:
            await shell(command=cmd)
        except ToolError as e:
            assert "dangerous pattern" not in str(e).lower()

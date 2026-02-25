"""Tests for file_tools: file_edit, glob_find, grep_search."""

from __future__ import annotations

import stat
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from sage.exceptions import ToolError
from sage.tools.file_tools import file_edit, glob_find, grep_search


class TestFileEdit:
    async def test_single_replacement(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "test.py"
        f.write_text("def hello():\n    return 'world'\n")

        result = await file_edit(
            path=str(f), old_string="return 'world'", new_string="return 'universe'"
        )
        assert "1 replacement" in result
        assert f.read_text() == "def hello():\n    return 'universe'\n"

    async def test_no_match_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "test.py"
        f.write_text("hello world")

        with pytest.raises(ToolError, match="not found"):
            await file_edit(path=str(f), old_string="xyz", new_string="abc")

    async def test_ambiguous_match_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "test.py"
        f.write_text("aaa\naaa\n")

        with pytest.raises(ToolError, match="ambiguous"):
            await file_edit(path=str(f), old_string="aaa", new_string="bbb")

    async def test_replace_all(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "test.py"
        f.write_text("foo bar foo baz foo")

        result = await file_edit(path=str(f), old_string="foo", new_string="qux", replace_all=True)
        assert "3 replacement" in result
        assert f.read_text() == "qux bar qux baz qux"

    async def test_missing_file_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ToolError, match="not found"):
            await file_edit(path=str(tmp_path / "nonexistent.py"), old_string="a", new_string="b")

    async def test_preserves_indentation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "test.py"
        f.write_text("    x = 1\n    y = 2\n")

        await file_edit(path=str(f), old_string="    x = 1", new_string="    x = 42")
        assert f.read_text() == "    x = 42\n    y = 2\n"


class TestGlobFind:
    async def test_finds_python_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("pass")
        (tmp_path / "b.py").write_text("pass")
        (tmp_path / "c.txt").write_text("text")

        result = await glob_find(pattern="*.py", path=str(tmp_path))
        assert "a.py" in result
        assert "b.py" in result
        assert "c.txt" not in result

    async def test_no_matches_returns_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = await glob_find(pattern="*.xyz", path=str(tmp_path))
        assert "no matches" in result.lower() or result.strip() == ""


class TestGrepSearch:
    async def test_finds_pattern_in_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("def hello():\n    pass\n")
        (tmp_path / "b.py").write_text("def world():\n    pass\n")

        result = await grep_search(pattern="hello", path=str(tmp_path))
        assert "hello" in result
        assert "a.py" in result

    async def test_glob_filter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("target_string")
        (tmp_path / "b.txt").write_text("target_string")

        result = await grep_search(pattern="target_string", path=str(tmp_path), glob="*.py")
        assert "a.py" in result
        # b.txt should be excluded by glob filter
        assert "b.txt" not in result

    async def test_no_matches_returns_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("nothing here")
        result = await grep_search(pattern="zzz_not_found_zzz", path=str(tmp_path))
        assert "no matches" in result.lower() or result.strip() == ""


class TestGrepPatternInjection:
    async def test_pattern_starting_with_dash_not_treated_as_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pattern starting with '-' should not be interpreted as a ripgrep flag."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("-flag-like-text\n")
        result = await grep_search(pattern="-flag-like-text", path=str(tmp_path))
        assert "flag-like-text" in result or "no matches" in result.lower()


class TestGrepExitCodes:
    async def test_rg_exit_code_2_raises_error(self) -> None:
        """ripgrep exit code >= 2 means an error occurred."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"rg: some error"))
        mock_proc.returncode = 2

        with patch("sage.tools.file_tools.asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(ToolError, match="grep_search failed"):
                await grep_search(pattern="test", path=".")


class TestFileEditPathTraversal:
    async def test_edit_outside_cwd_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ToolError, match="Access denied"):
            await file_edit(path="/etc/hosts", old_string="x", new_string="y")

    async def test_edit_traversal_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ToolError, match="Access denied"):
            await file_edit(path="../../etc/hosts", old_string="x", new_string="y")

    async def test_glob_outside_cwd_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ToolError, match="Access denied"):
            await glob_find(pattern="*", path="/etc")

    async def test_grep_outside_cwd_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ToolError, match="Access denied"):
            await grep_search(pattern="password", path="/etc")


class TestFileEditPermissions:
    async def test_preserves_executable_bit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "script.sh"
        f.write_text("#!/bin/bash\necho old\n")
        f.chmod(0o755)

        await file_edit(path=str(f), old_string="echo old", new_string="echo new")

        mode = f.stat().st_mode
        assert mode & stat.S_IXUSR, "User executable bit was lost"
        assert mode & stat.S_IXGRP, "Group executable bit was lost"

"""Tests for file_tools: file_edit, glob_find, grep_search."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from sage.exceptions import ToolError
from sage.tools.file_tools import file_edit


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

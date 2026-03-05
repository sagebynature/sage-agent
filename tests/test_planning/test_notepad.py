from __future__ import annotations

from pathlib import Path


from sage.planning.notepad import Notepad


class TestNotepadWrite:
    async def test_write_creates_section_file(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-a", base_dir=tmp_path)
        await notepad.write("learnings", "Python is great")
        assert (tmp_path / "plan-a" / "learnings.md").exists()

    async def test_write_appends_by_default(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-a", base_dir=tmp_path)
        await notepad.write("notes", "line one")
        await notepad.write("notes", "line two")
        content = (tmp_path / "plan-a" / "notes.md").read_text()
        assert "line one" in content
        assert "line two" in content

    async def test_write_overwrite_replaces_content(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-a", base_dir=tmp_path)
        await notepad.write("notes", "original", append=False)
        await notepad.write("notes", "replacement", append=False)
        content = (tmp_path / "plan-a" / "notes.md").read_text()
        assert "replacement" in content
        assert "original" not in content

    async def test_write_appends_newline(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-a", base_dir=tmp_path)
        await notepad.write("notes", "entry")
        raw = (tmp_path / "plan-a" / "notes.md").read_text()
        assert raw.endswith("\n")


class TestNotepadRead:
    async def test_read_returns_content(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-b", base_dir=tmp_path)
        await notepad.write("decisions", "use sqlite")
        assert "use sqlite" in await notepad.read("decisions")

    async def test_read_returns_empty_string_for_missing_section(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-b", base_dir=tmp_path)
        assert await notepad.read("nonexistent") == ""

    async def test_read_returns_all_written_content(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-b", base_dir=tmp_path)
        await notepad.write("decisions", "line one")
        await notepad.write("decisions", "line two")
        content = await notepad.read("decisions")
        assert "line one" in content
        assert "line two" in content


class TestNotepadReadAll:
    async def test_read_all_returns_empty_for_new_notepad(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-c", base_dir=tmp_path)
        assert await notepad.read_all() == ""

    async def test_read_all_includes_all_sections(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-c", base_dir=tmp_path)
        await notepad.write("learnings", "learned X")
        await notepad.write("decisions", "decided Y")
        result = await notepad.read_all()
        assert "learned X" in result
        assert "decided Y" in result

    async def test_read_all_uses_section_headers(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-c", base_dir=tmp_path)
        await notepad.write("learnings", "something")
        result = await notepad.read_all()
        assert "### LEARNINGS" in result

    async def test_read_all_skips_empty_sections(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-c", base_dir=tmp_path)
        (tmp_path / "plan-c" / "empty.md").write_text("   \n")
        await notepad.write("notes", "actual content")
        result = await notepad.read_all()
        assert "### EMPTY" not in result
        assert "### NOTES" in result


class TestNotepadClear:
    async def test_clear_removes_section_file(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-d", base_dir=tmp_path)
        await notepad.write("todo", "task 1")
        notepad.clear("todo")
        assert not (tmp_path / "plan-d" / "todo.md").exists()

    def test_clear_nonexistent_section_is_noop(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-d", base_dir=tmp_path)
        notepad.clear("ghost")

    async def test_cleared_section_reads_empty(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-d", base_dir=tmp_path)
        await notepad.write("todo", "task 1")
        notepad.clear("todo")
        assert await notepad.read("todo") == ""


class TestNotepadIsolation:
    async def test_separate_plan_names_are_independent(self, tmp_path: Path) -> None:
        a = Notepad("plan-x", base_dir=tmp_path)
        b = Notepad("plan-y", base_dir=tmp_path)
        await a.write("notes", "x content")
        await b.write("notes", "y content")
        assert "x content" not in await b.read("notes")
        assert "y content" not in await a.read("notes")

    async def test_base_dir_is_respected(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom_dir"
        notepad = Notepad("myplan", base_dir=custom)
        await notepad.write("test", "hello")
        assert (custom / "myplan" / "test.md").exists()

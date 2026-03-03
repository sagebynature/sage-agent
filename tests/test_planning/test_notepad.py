from __future__ import annotations

from pathlib import Path


from sage.planning.notepad import Notepad


class TestNotepadWrite:
    def test_write_creates_section_file(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-a", base_dir=tmp_path)
        notepad.write("learnings", "Python is great")
        assert (tmp_path / "plan-a" / "learnings.md").exists()

    def test_write_appends_by_default(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-a", base_dir=tmp_path)
        notepad.write("notes", "line one")
        notepad.write("notes", "line two")
        content = (tmp_path / "plan-a" / "notes.md").read_text()
        assert "line one" in content
        assert "line two" in content

    def test_write_overwrite_replaces_content(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-a", base_dir=tmp_path)
        notepad.write("notes", "original", append=False)
        notepad.write("notes", "replacement", append=False)
        content = (tmp_path / "plan-a" / "notes.md").read_text()
        assert "replacement" in content
        assert "original" not in content

    def test_write_appends_newline(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-a", base_dir=tmp_path)
        notepad.write("notes", "entry")
        raw = (tmp_path / "plan-a" / "notes.md").read_text()
        assert raw.endswith("\n")


class TestNotepadRead:
    def test_read_returns_content(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-b", base_dir=tmp_path)
        notepad.write("decisions", "use sqlite")
        assert "use sqlite" in notepad.read("decisions")

    def test_read_returns_empty_string_for_missing_section(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-b", base_dir=tmp_path)
        assert notepad.read("nonexistent") == ""

    def test_read_returns_all_written_content(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-b", base_dir=tmp_path)
        notepad.write("decisions", "line one")
        notepad.write("decisions", "line two")
        content = notepad.read("decisions")
        assert "line one" in content
        assert "line two" in content


class TestNotepadReadAll:
    def test_read_all_returns_empty_for_new_notepad(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-c", base_dir=tmp_path)
        assert notepad.read_all() == ""

    def test_read_all_includes_all_sections(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-c", base_dir=tmp_path)
        notepad.write("learnings", "learned X")
        notepad.write("decisions", "decided Y")
        result = notepad.read_all()
        assert "learned X" in result
        assert "decided Y" in result

    def test_read_all_uses_section_headers(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-c", base_dir=tmp_path)
        notepad.write("learnings", "something")
        result = notepad.read_all()
        assert "### LEARNINGS" in result

    def test_read_all_skips_empty_sections(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-c", base_dir=tmp_path)
        (tmp_path / "plan-c" / "empty.md").write_text("   \n")
        notepad.write("notes", "actual content")
        result = notepad.read_all()
        assert "### EMPTY" not in result
        assert "### NOTES" in result


class TestNotepadClear:
    def test_clear_removes_section_file(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-d", base_dir=tmp_path)
        notepad.write("todo", "task 1")
        notepad.clear("todo")
        assert not (tmp_path / "plan-d" / "todo.md").exists()

    def test_clear_nonexistent_section_is_noop(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-d", base_dir=tmp_path)
        notepad.clear("ghost")

    def test_cleared_section_reads_empty(self, tmp_path: Path) -> None:
        notepad = Notepad("plan-d", base_dir=tmp_path)
        notepad.write("todo", "task 1")
        notepad.clear("todo")
        assert notepad.read("todo") == ""


class TestNotepadIsolation:
    def test_separate_plan_names_are_independent(self, tmp_path: Path) -> None:
        a = Notepad("plan-x", base_dir=tmp_path)
        b = Notepad("plan-y", base_dir=tmp_path)
        a.write("notes", "x content")
        b.write("notes", "y content")
        assert "x content" not in b.read("notes")
        assert "y content" not in a.read("notes")

    def test_base_dir_is_respected(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom_dir"
        notepad = Notepad("myplan", base_dir=custom)
        notepad.write("test", "hello")
        assert (custom / "myplan" / "test.md").exists()

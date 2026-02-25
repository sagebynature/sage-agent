"""Tests for the skill file loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from sage.exceptions import ConfigError
from sage.skills.loader import Skill, load_skill, load_skills_from_directory


class TestLoadSkill:
    def test_skill_with_frontmatter(self, tmp_path: Path) -> None:
        skill_file = tmp_path / "search.md"
        skill_file.write_text(
            """\
---
name: web-search
description: Search the web for information
---
Use this skill to perform web searches.

## Usage
Provide a query string.
""",
            encoding="utf-8",
        )
        skill = load_skill(skill_file)

        assert skill.name == "web-search"
        assert skill.description == "Search the web for information"
        assert "Use this skill to perform web searches." in skill.content
        assert "## Usage" in skill.content

    def test_skill_without_frontmatter_uses_filename(self, tmp_path: Path) -> None:
        skill_file = tmp_path / "my-skill.md"
        skill_file.write_text("Just some content.\nMore content.", encoding="utf-8")

        skill = load_skill(skill_file)

        assert skill.name == "my-skill"
        assert skill.description == ""
        assert skill.content == "Just some content.\nMore content."

    def test_skill_with_empty_frontmatter(self, tmp_path: Path) -> None:
        skill_file = tmp_path / "empty-meta.md"
        skill_file.write_text("---\n---\nBody text here.", encoding="utf-8")

        skill = load_skill(skill_file)

        assert skill.name == "empty-meta"
        assert skill.description == ""
        assert skill.content == "Body text here."

    def test_skill_with_partial_frontmatter(self, tmp_path: Path) -> None:
        skill_file = tmp_path / "partial.md"
        skill_file.write_text(
            """\
---
name: custom-name
---
Content goes here.
""",
            encoding="utf-8",
        )
        skill = load_skill(skill_file)

        assert skill.name == "custom-name"
        assert skill.description == ""
        assert skill.content == "Content goes here."

    def test_skill_with_unclosed_frontmatter(self, tmp_path: Path) -> None:
        skill_file = tmp_path / "unclosed.md"
        skill_file.write_text("---\nname: broken\nNo closing delimiter.", encoding="utf-8")

        skill = load_skill(skill_file)

        # Treated as no frontmatter
        assert skill.name == "unclosed"
        assert "---" in skill.content

    def test_missing_file_raises_config_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="Skill file not found"):
            load_skill(tmp_path / "nonexistent.md")

    def test_skill_with_invalid_yaml_frontmatter(self, tmp_path: Path) -> None:
        skill_file = tmp_path / "bad-yaml.md"
        skill_file.write_text("---\n[invalid: yaml: :\n---\nBody.", encoding="utf-8")

        skill = load_skill(skill_file)

        # Falls back to treating entire text as content
        assert skill.name == "bad-yaml"
        assert skill.description == ""

    def test_empty_file(self, tmp_path: Path) -> None:
        skill_file = tmp_path / "empty.md"
        skill_file.write_text("", encoding="utf-8")

        skill = load_skill(skill_file)

        assert skill.name == "empty"
        assert skill.content == ""


class TestLoadSkillsFromDirectory:
    def test_loads_all_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "alpha.md").write_text(
            "---\nname: alpha\n---\nAlpha content.", encoding="utf-8"
        )
        (tmp_path / "beta.md").write_text("Beta content.", encoding="utf-8")
        (tmp_path / "not-a-skill.txt").write_text("Ignored.", encoding="utf-8")

        skills = load_skills_from_directory(tmp_path)

        assert len(skills) == 2
        names = [s.name for s in skills]
        assert "alpha" in names
        assert "beta" in names

    def test_returns_empty_list_for_no_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "readme.txt").write_text("Not a skill.", encoding="utf-8")

        skills = load_skills_from_directory(tmp_path)
        assert skills == []

    def test_nonexistent_directory_raises_config_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="Skills directory not found"):
            load_skills_from_directory(tmp_path / "no-such-dir")

    def test_skills_sorted_by_file_name(self, tmp_path: Path) -> None:
        (tmp_path / "c-skill.md").write_text("C", encoding="utf-8")
        (tmp_path / "a-skill.md").write_text("A", encoding="utf-8")
        (tmp_path / "b-skill.md").write_text("B", encoding="utf-8")

        skills = load_skills_from_directory(tmp_path)

        assert [s.name for s in skills] == ["a-skill", "b-skill", "c-skill"]


class TestSkillModel:
    def test_defaults(self) -> None:
        skill = Skill(name="test")
        assert skill.description == ""
        assert skill.content == ""

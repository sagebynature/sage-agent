from __future__ import annotations

from pathlib import Path

from sage.skills.loader import resolve_skills_dir, filter_skills_by_names


def test_config_skills_dir_takes_precedence(tmp_path: Path) -> None:
    config_skills = tmp_path / "config-skills"
    config_skills.mkdir()

    resolved = resolve_skills_dir(str(config_skills))

    assert resolved == config_skills


def test_config_skills_dir_nonexistent_skipped(tmp_path: Path, monkeypatch) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: cwd))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    missing = tmp_path / "missing-config-skills"

    resolved = resolve_skills_dir(str(missing))

    assert resolved is None


def test_waterfall_cwd_skills_first(tmp_path: Path, monkeypatch) -> None:
    cwd_skills = tmp_path / "skills"
    cwd_skills.mkdir()
    monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: tmp_path))

    resolved = resolve_skills_dir()

    assert resolved == cwd_skills


def test_waterfall_home_agents_skills_second(tmp_path: Path, monkeypatch) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    agents_skills = tmp_path / ".agents" / "skills"
    agents_skills.mkdir(parents=True)
    monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: cwd))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    resolved = resolve_skills_dir()

    assert resolved == agents_skills


def test_waterfall_home_claude_skills_third(tmp_path: Path, monkeypatch) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    claude_skills = tmp_path / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: cwd))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    resolved = resolve_skills_dir()

    assert resolved == claude_skills


def test_waterfall_none_when_nothing_exists(tmp_path: Path, monkeypatch) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: cwd))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    resolved = resolve_skills_dir()

    assert resolved is None


def test_waterfall_stops_at_first_match(tmp_path: Path, monkeypatch) -> None:
    cwd_skills = tmp_path / "cwd" / "skills"
    cwd_skills.mkdir(parents=True)
    agents_skills = tmp_path / ".agents" / "skills"
    agents_skills.mkdir(parents=True)
    monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: tmp_path / "cwd"))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    resolved = resolve_skills_dir()

    assert resolved == cwd_skills


class TestFilterSkillsByNames:
    def test_filter_returns_all_when_names_none(self):
        from sage.skills.loader import Skill

        skills = [Skill(name="a", content="x"), Skill(name="b", content="y")]
        result = filter_skills_by_names(skills, None)
        assert result == skills

    def test_filter_returns_empty_when_names_empty(self):
        from sage.skills.loader import Skill

        skills = [Skill(name="a", content="x"), Skill(name="b", content="y")]
        result = filter_skills_by_names(skills, [])
        assert result == []

    def test_filter_returns_matching_skills_only(self):
        from sage.skills.loader import Skill

        skills = [
            Skill(name="git-master", content="x"),
            Skill(name="terraform", content="y"),
            Skill(name="python", content="z"),
        ]
        result = filter_skills_by_names(skills, ["git-master"])
        assert len(result) == 1
        assert result[0].name == "git-master"

    def test_filter_ignores_unknown_names(self):
        from sage.skills.loader import Skill

        skills = [Skill(name="a", content="x")]
        result = filter_skills_by_names(skills, ["nonexistent"])
        assert result == []

    def test_filter_preserves_pool_order(self):
        from sage.skills.loader import Skill

        skills = [
            Skill(name="c", content="z"),
            Skill(name="a", content="x"),
            Skill(name="b", content="y"),
        ]
        result = filter_skills_by_names(skills, ["b", "a"])
        assert [s.name for s in result] == ["a", "b"]

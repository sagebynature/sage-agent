"""Skill file loader for Sage.

Skills are markdown files with optional YAML frontmatter that define
reusable capabilities for agents.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel

from sage.exceptions import ConfigError
from sage.frontmatter import parse_frontmatter


class Skill(BaseModel):
    """A loaded skill definition."""

    name: str
    description: str = ""
    content: str = ""


def load_skill(path: str | Path) -> Skill:
    """Load a markdown skill file with optional YAML frontmatter.

    The frontmatter is delimited by ``---`` lines at the start of the file
    and may contain ``name`` and ``description`` fields.  If no frontmatter
    is present, the skill name is derived from the filename (stem).

    Args:
        path: Path to a ``.md`` skill file.

    Returns:
        A :class:`Skill` instance.

    Raises:
        ConfigError: If the file cannot be found or read.
    """
    skill_path = Path(path)
    if not skill_path.exists():
        raise ConfigError(f"Skill file not found: {skill_path}")

    try:
        raw = skill_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Failed to read skill file {skill_path}: {exc}") from exc

    meta, content = parse_frontmatter(raw)

    name = meta.get("name", "")
    description = meta.get("description", "")

    if not name:
        name = skill_path.stem

    return Skill(name=name, description=description, content=content)


def load_skills_from_directory(directory: str | Path) -> list[Skill]:
    """Load skills from a directory.

    Supports two layouts (which may be mixed within the same directory):

    - **Flat** — ``skills/code-review.md``
    - **Directory-per-skill** — ``skills/code-review/skill.md``

    For directory entries the loader searches in order:

    1. ``skill.md`` inside the directory
    2. ``{directory_name}.md`` inside the directory  (e.g. ``code-review/code-review.md``)
    3. Any single ``.md`` file found in the directory

    When no frontmatter ``name`` is present the directory name is used as the
    skill name (rather than the file stem, which would typically be "skill").

    Args:
        directory: Path to a directory containing skill files or sub-directories.

    Returns:
        A list of :class:`Skill` instances, sorted by entry name.

    Raises:
        ConfigError: If the directory does not exist.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise ConfigError(f"Skills directory not found: {dir_path}")

    skills: list[Skill] = []
    for entry in sorted(dir_path.iterdir()):
        if entry.is_file() and entry.suffix == ".md":
            skills.append(load_skill(entry))
        elif entry.is_dir():
            skill = _load_skill_from_dir(entry)
            if skill is not None:
                skills.append(skill)
    return skills


def _load_skill_from_dir(skill_dir: Path) -> Skill | None:
    """Load a skill from a per-skill directory.

    Searches for a skill file in the following order:

    1. ``skill.md``
    2. ``{skill_dir.name}.md``
    3. First ``.md`` file found (alphabetical)

    When the skill file has no frontmatter ``name`` the directory name is used
    instead of the file stem.

    Returns:
        A :class:`Skill` instance, or ``None`` if no ``.md`` file exists.
    """
    candidates = [
        skill_dir / "skill.md",
        skill_dir / f"{skill_dir.name}.md",
    ]
    skill_file: Path | None = None
    for candidate in candidates:
        if candidate.exists():
            skill_file = candidate
            break

    if skill_file is None:
        md_files = sorted(skill_dir.glob("*.md"))
        if md_files:
            skill_file = md_files[0]

    if skill_file is None:
        return None

    skill = load_skill(skill_file)
    # If the name was auto-derived from the file stem (e.g. "skill"),
    # replace it with the more meaningful directory name.
    if skill.name == skill_file.stem:
        skill = skill.model_copy(update={"name": skill_dir.name})
    return skill


def resolve_skills_dir(config_skills_dir: str | None = None) -> Path | None:
    """Resolve the global skills directory using waterfall lookup.

    Resolution order:
    1. config.toml top-level skills_dir (if set and is a directory)
    2. ./skills in current working directory
    3. ~/.agents/skills
    4. ~/.claude/skills
    5. None (no skills directory found)
    """
    if config_skills_dir is not None:
        expanded = os.path.expandvars(config_skills_dir)
        p = Path(expanded).expanduser()
        if p.is_dir():
            return p

    candidates = [
        Path.cwd() / "skills",
        Path.home() / ".agents" / "skills",
        Path.home() / ".claude" / "skills",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate

    return None


def filter_skills_by_names(skills: list[Skill], names: list[str] | None) -> list[Skill]:
    """Filter a skill pool by an allowlist of names.

    Args:
        skills: The global skill pool to filter.
        names: Allowlist of skill names.
            - ``None`` — return all skills (no filtering)
            - ``[]`` — return no skills (empty allowlist)
            - ``["x", "y"]`` — return only skills whose name is in the list

    Returns:
        Filtered list preserving pool order (not allowlist order).
    """
    if names is None:
        return skills
    name_set = set(names)
    return [s for s in skills if s.name in name_set]

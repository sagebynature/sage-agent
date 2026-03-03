from __future__ import annotations

from pathlib import Path


class Notepad:
    """Persistent markdown working memory scoped to a named plan.

    Notes are stored as ``.md`` files under ``.sage/notepads/<plan_name>/``.
    Each *section* maps to one file so that different topics (e.g.
    ``learnings``, ``decisions``, ``todo``) can be managed independently.
    """

    def __init__(self, plan_name: str, *, base_dir: Path | None = None) -> None:
        self.plan_name = plan_name
        root = base_dir if base_dir is not None else Path(".sage/notepads")
        self.base_dir = root / plan_name
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def write(self, section: str, content: str, *, append: bool = True) -> None:
        path = self.base_dir / f"{section}.md"
        mode = "a" if append else "w"
        with path.open(mode) as fh:
            fh.write(content + "\n")

    def read(self, section: str) -> str:
        path = self.base_dir / f"{section}.md"
        if not path.exists():
            return ""
        return path.read_text()

    def read_all(self) -> str:
        sections: list[str] = []
        for path in sorted(self.base_dir.glob("*.md")):
            content = path.read_text()
            if content.strip():
                sections.append(f"### {path.stem.upper()}\n{content}")
        return "\n\n".join(sections)

    def clear(self, section: str) -> None:
        path = self.base_dir / f"{section}.md"
        if path.exists():
            path.unlink()

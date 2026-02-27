"""File-based memory backend with JSON and Markdown storage modes."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from sage.memory.base import MemoryEntry
from sage.models import Message

logger = logging.getLogger(__name__)


class FileMemory:
    """File-based MemoryProtocol implementation.

    JSON mode: single {path}.json file with list of serialized MemoryEntry dicts.
    Markdown mode: one {id}.md file per entry in {path}/ directory.
      Filename: {id}.md
      Content: # {first line of content}\\n\\n{content}\\n\\n<!-- metadata: {json} -->

    Recall uses keyword scoring (no embeddings):
      - Split query into words
      - Score each entry by word overlap with content + metadata values
      - Return top limit matches sorted by score desc
    """

    def __init__(
        self,
        path: str | Path,
        *,
        format: Literal["json", "markdown"] = "json",
    ) -> None:
        self._path = Path(path)
        self._format = format

    # ------------------------------------------------------------------
    # MemoryProtocol methods
    # ------------------------------------------------------------------

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store content and return the assigned memory ID."""
        meta = metadata or {}
        memory_id = uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        entry = MemoryEntry(
            id=memory_id,
            content=content,
            metadata=meta,
            score=0.0,
            created_at=created_at,
        )
        if self._format == "json":
            self._json_append(entry)
        else:
            self._markdown_write(entry)
        logger.debug("FileMemory stored id=%s content_preview=%.80s", memory_id, content)
        return memory_id

    async def recall(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Recall memories using keyword scoring (no embeddings)."""
        all_entries = self._load_all()
        if not all_entries:
            return []

        query_words = _tokenize(query)
        if not query_words:
            return all_entries[:limit]

        scored: list[tuple[float, MemoryEntry]] = []
        for entry in all_entries:
            score = _keyword_score(query_words, entry)
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda t: t[0], reverse=True)
        result = []
        for score, entry in scored[:limit]:
            entry_with_score = entry.model_copy(update={"score": score})
            result.append(entry_with_score)
        return result

    async def compact(self, messages: list[Message]) -> list[Message]:
        """No-op compaction — returns messages unchanged."""
        return messages

    async def clear(self) -> None:
        """Remove all stored memories."""
        if self._format == "json":
            if self._path.exists():
                self._path.write_text("[]", encoding="utf-8")
                logger.debug("FileMemory (json) cleared: %s", self._path)
        else:
            if self._path.is_dir():
                for md_file in self._path.glob("*.md"):
                    md_file.unlink()
                logger.debug("FileMemory (markdown) cleared: %s", self._path)

    # ------------------------------------------------------------------
    # Enriched MemoryProtocol methods (Task 5 extension)
    # ------------------------------------------------------------------

    async def get(self, memory_id: str) -> MemoryEntry | None:
        """Return a single entry by ID, or None if not found."""
        for entry in self._load_all():
            if entry.id == memory_id:
                return entry
        return None

    async def list_entries(self, *, limit: int = 50, offset: int = 0) -> list[MemoryEntry]:
        """Return a paginated list of all entries."""
        all_entries = self._load_all()
        return all_entries[offset : offset + limit]

    async def forget(self, memory_id: str) -> bool:
        """Delete a specific memory entry by ID. Returns True if deleted, False if not found."""
        if self._format == "json":
            return self._json_forget(memory_id)
        else:
            return self._markdown_forget(memory_id)

    async def count(self) -> int:
        """Return the total number of stored entries."""
        return len(self._load_all())

    async def health_check(self) -> dict[str, Any]:
        """Return a health status dict."""
        try:
            count = len(self._load_all())
            return {
                "status": "ok",
                "format": self._format,
                "path": str(self._path),
                "count": count,
            }
        except Exception as exc:
            return {
                "status": "error",
                "format": self._format,
                "path": str(self._path),
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # JSON backend internals
    # ------------------------------------------------------------------

    def _json_load(self) -> list[MemoryEntry]:
        """Load all entries from the JSON file."""
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return [MemoryEntry(**d) for d in data]
        except Exception as exc:
            logger.warning("FileMemory failed to load JSON at %s: %s", self._path, exc)
            return []

    def _json_save(self, entries: list[MemoryEntry]) -> None:
        """Write all entries to the JSON file, creating parent dirs as needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [e.model_dump() for e in entries]
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _json_append(self, entry: MemoryEntry) -> None:
        """Append a single entry to the JSON file."""
        entries = self._json_load()
        entries.append(entry)
        self._json_save(entries)

    def _json_forget(self, memory_id: str) -> bool:
        """Remove an entry by ID from JSON storage. Returns True if found."""
        entries = self._json_load()
        new_entries = [e for e in entries if e.id != memory_id]
        if len(new_entries) == len(entries):
            return False
        self._json_save(new_entries)
        return True

    # ------------------------------------------------------------------
    # Markdown backend internals
    # ------------------------------------------------------------------

    def _markdown_path(self, memory_id: str) -> Path:
        return self._path / f"{memory_id}.md"

    def _markdown_write(self, entry: MemoryEntry) -> None:
        """Write a MemoryEntry as a Markdown file."""
        self._path.mkdir(parents=True, exist_ok=True)
        first_line = entry.content.split("\n")[0]
        meta_json = json.dumps(entry.model_dump())
        file_content = f"# {first_line}\n\n{entry.content}\n\n<!-- metadata: {meta_json} -->"
        self._markdown_path(entry.id).write_text(file_content, encoding="utf-8")

    def _markdown_read(self, md_file: Path) -> MemoryEntry | None:
        """Parse a Markdown file back into a MemoryEntry."""
        try:
            text = md_file.read_text(encoding="utf-8")
            match = re.search(r"<!-- metadata: (.+?) -->", text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                return MemoryEntry(**data)
            # Fallback: derive from filename and content
            memory_id = md_file.stem
            lines = text.split("\n")
            # Strip title line and trailing metadata comment
            content_lines = [
                line
                for line in lines
                if not line.startswith("# ") and not line.startswith("<!-- metadata")
            ]
            content = "\n".join(content_lines).strip()
            return MemoryEntry(id=memory_id, content=content, metadata={}, score=0.0, created_at="")
        except Exception as exc:
            logger.warning("FileMemory failed to parse %s: %s", md_file, exc)
            return None

    def _markdown_forget(self, memory_id: str) -> bool:
        """Delete a Markdown entry file. Returns True if it existed."""
        md_file = self._markdown_path(memory_id)
        if md_file.exists():
            md_file.unlink()
            return True
        return False

    def _markdown_load_all(self) -> list[MemoryEntry]:
        """Load all Markdown entries from the directory."""
        if not self._path.is_dir():
            return []
        entries: list[MemoryEntry] = []
        for md_file in sorted(self._path.glob("*.md")):
            entry = self._markdown_read(md_file)
            if entry is not None:
                entries.append(entry)
        return entries

    # ------------------------------------------------------------------
    # Unified loader
    # ------------------------------------------------------------------

    def _load_all(self) -> list[MemoryEntry]:
        """Load all entries regardless of format."""
        if self._format == "json":
            return self._json_load()
        else:
            return self._markdown_load_all()


# ------------------------------------------------------------------
# Keyword scoring helpers
# ------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s]")


def _tokenize(text: str) -> set[str]:
    """Lowercase and split text into a set of word tokens."""
    cleaned = _PUNCT_RE.sub(" ", text.lower())
    return {w for w in cleaned.split() if w}


def _keyword_score(query_words: set[str], entry: MemoryEntry) -> float:
    """Score an entry by the fraction of query words that appear in its content + metadata."""
    if not query_words:
        return 0.0

    # Build a corpus from content and all metadata string values.
    corpus_parts = [entry.content]
    for v in entry.metadata.values():
        if isinstance(v, str):
            corpus_parts.append(v)
        else:
            corpus_parts.append(str(v))
    corpus_words = _tokenize(" ".join(corpus_parts))

    matching = query_words & corpus_words
    if not matching:
        return 0.0
    return len(matching) / len(query_words)

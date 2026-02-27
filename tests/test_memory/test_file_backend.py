"""Tests for FileMemory backend (JSON and Markdown modes)."""

from __future__ import annotations

from typing import Any

import pytest

from sage.memory.file_backend import FileMemory
from sage.memory.base import MemoryEntry


# ---------------------------------------------------------------------------
# JSON mode tests
# ---------------------------------------------------------------------------


class TestJSONMode:
    @pytest.mark.asyncio
    async def test_json_store_recall(self, tmp_path: Any) -> None:
        """Store 2 entries, recall the relevant one (JSON mode)."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        await mem.store("the python programming language", {"tag": "tech"})
        await mem.store("french cuisine recipes", {"tag": "food"})

        results = await mem.recall("python programming", limit=1)
        assert len(results) == 1
        assert "python" in results[0].content.lower()

    @pytest.mark.asyncio
    async def test_json_count(self, tmp_path: Any) -> None:
        """Store 3 entries, count() returns 3."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        await mem.store("entry one", {})
        await mem.store("entry two", {})
        await mem.store("entry three", {})

        assert await mem.count() == 3

    @pytest.mark.asyncio
    async def test_json_list_entries(self, tmp_path: Any) -> None:
        """Store 3 entries, list_entries(limit=2) returns 2."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        await mem.store("alpha", {})
        await mem.store("beta", {})
        await mem.store("gamma", {})

        results = await mem.list_entries(limit=2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_json_get(self, tmp_path: Any) -> None:
        """Store, list to get id, get(id) returns entry."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        await mem.store("hello world", {"key": "value"})

        entries = await mem.list_entries()
        assert len(entries) == 1
        entry_id = entries[0].id

        result = await mem.get(entry_id)
        assert result is not None
        assert result.id == entry_id
        assert result.content == "hello world"
        assert result.metadata == {"key": "value"}

    @pytest.mark.asyncio
    async def test_json_forget(self, tmp_path: Any) -> None:
        """Store, forget(id) returns True, count() returns 0."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        await mem.store("to be forgotten", {})

        entries = await mem.list_entries()
        entry_id = entries[0].id

        result = await mem.forget(entry_id)
        assert result is True
        assert await mem.count() == 0

    @pytest.mark.asyncio
    async def test_json_forget_missing(self, tmp_path: Any) -> None:
        """forget('nonexistent') returns False."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        result = await mem.forget("nonexistent_id_xyz")
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_json(self, tmp_path: Any) -> None:
        """Store 2 entries, clear(), count() returns 0."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        await mem.store("one", {})
        await mem.store("two", {})
        await mem.clear()

        assert await mem.count() == 0

    @pytest.mark.asyncio
    async def test_json_get_missing_returns_none(self, tmp_path: Any) -> None:
        """get() with a non-existent id returns None."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        result = await mem.get("does_not_exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_json_list_entries_offset(self, tmp_path: Any) -> None:
        """list_entries supports offset pagination."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        for i in range(5):
            await mem.store(f"entry {i}", {})

        await mem.list_entries(limit=50)
        paginated = await mem.list_entries(limit=50, offset=2)
        assert len(paginated) == 3

    @pytest.mark.asyncio
    async def test_parent_dirs_created(self, tmp_path: Any) -> None:
        """Store to nested path, dirs are created automatically."""
        nested_path = tmp_path / "a" / "b" / "c" / "mem.json"
        mem = FileMemory(nested_path, format="json")
        await mem.store("nested dir test", {})

        assert nested_path.exists()
        assert await mem.count() == 1

    @pytest.mark.asyncio
    async def test_health_check_json(self, tmp_path: Any) -> None:
        """health_check() returns dict with status='ok'."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        result = await mem.health_check()
        assert isinstance(result, dict)
        assert result.get("status") == "ok"

    @pytest.mark.asyncio
    async def test_compact_noop(self, tmp_path: Any) -> None:
        """compact() is a no-op and does not raise."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        await mem.store("some entry", {})
        # compact takes messages list (MemoryProtocol compat)
        from sage.models import Message

        msgs = [Message(role="user", content="hi")]
        result = await mem.compact(msgs)
        # Should return messages unchanged
        assert result == msgs

    @pytest.mark.asyncio
    async def test_store_returns_id(self, tmp_path: Any) -> None:
        """store() returns a memory ID string."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        mid = await mem.store("test content", {})
        assert isinstance(mid, str)
        assert len(mid) == 32  # uuid4().hex

    @pytest.mark.asyncio
    async def test_recall_returns_memory_entries(self, tmp_path: Any) -> None:
        """recall() returns MemoryEntry instances."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        await mem.store("machine learning algorithms", {})
        results = await mem.recall("machine learning")
        assert all(isinstance(r, MemoryEntry) for r in results)

    @pytest.mark.asyncio
    async def test_recall_respects_limit(self, tmp_path: Any) -> None:
        """recall() respects the limit parameter."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        for i in range(10):
            await mem.store(f"common keyword entry {i}", {})
        results = await mem.recall("common keyword", limit=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_recall_sorted_by_score_desc(self, tmp_path: Any) -> None:
        """recall() returns entries sorted by score descending."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        await mem.store("python snake reptile", {})
        await mem.store("python programming language code", {})
        await mem.store("completely unrelated topic", {})
        results = await mem.recall("python programming", limit=10)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_recall_empty_returns_empty(self, tmp_path: Any) -> None:
        """recall() on empty storage returns []."""
        mem = FileMemory(tmp_path / "mem.json", format="json")
        results = await mem.recall("anything")
        assert results == []


# ---------------------------------------------------------------------------
# Markdown mode tests
# ---------------------------------------------------------------------------


class TestMarkdownMode:
    @pytest.mark.asyncio
    async def test_markdown_store_creates_files(self, tmp_path: Any) -> None:
        """Store 2 entries, directory has 2 .md files."""
        mem_dir = tmp_path / "memories"
        mem = FileMemory(mem_dir, format="markdown")
        await mem.store("first memory entry", {"source": "test"})
        await mem.store("second memory entry", {"source": "test2"})

        md_files = list(mem_dir.glob("*.md"))
        assert len(md_files) == 2

    @pytest.mark.asyncio
    async def test_markdown_recall(self, tmp_path: Any) -> None:
        """Store 2 entries, recall by keyword returns relevant one."""
        mem_dir = tmp_path / "memories"
        mem = FileMemory(mem_dir, format="markdown")
        await mem.store("deep learning neural networks", {"field": "AI"})
        await mem.store("cooking pasta carbonara recipe", {"field": "food"})

        results = await mem.recall("neural networks deep learning", limit=1)
        assert len(results) == 1
        assert "neural" in results[0].content.lower() or "learning" in results[0].content.lower()

    @pytest.mark.asyncio
    async def test_clear_markdown(self, tmp_path: Any) -> None:
        """Store 2 entries, clear(), no .md files remain."""
        mem_dir = tmp_path / "memories"
        mem = FileMemory(mem_dir, format="markdown")
        await mem.store("first", {})
        await mem.store("second", {})
        await mem.clear()

        md_files = list(mem_dir.glob("*.md"))
        assert len(md_files) == 0

    @pytest.mark.asyncio
    async def test_markdown_count(self, tmp_path: Any) -> None:
        """count() returns correct number for markdown mode."""
        mem_dir = tmp_path / "memories"
        mem = FileMemory(mem_dir, format="markdown")
        await mem.store("one", {})
        await mem.store("two", {})
        await mem.store("three", {})
        assert await mem.count() == 3

    @pytest.mark.asyncio
    async def test_markdown_forget(self, tmp_path: Any) -> None:
        """forget(id) deletes the .md file and returns True."""
        mem_dir = tmp_path / "memories"
        mem = FileMemory(mem_dir, format="markdown")
        await mem.store("forget me please", {})

        entries = await mem.list_entries()
        entry_id = entries[0].id

        result = await mem.forget(entry_id)
        assert result is True
        assert await mem.count() == 0
        # File should be gone
        md_files = list(mem_dir.glob("*.md"))
        assert len(md_files) == 0

    @pytest.mark.asyncio
    async def test_markdown_forget_missing(self, tmp_path: Any) -> None:
        """forget() with non-existent id returns False in markdown mode."""
        mem_dir = tmp_path / "memories"
        mem = FileMemory(mem_dir, format="markdown")
        result = await mem.forget("nonexistent_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_markdown_get(self, tmp_path: Any) -> None:
        """get(id) returns correct entry in markdown mode."""
        mem_dir = tmp_path / "memories"
        mem = FileMemory(mem_dir, format="markdown")
        await mem.store("markdown retrieval test", {"key": "val"})

        entries = await mem.list_entries()
        entry_id = entries[0].id

        result = await mem.get(entry_id)
        assert result is not None
        assert result.content == "markdown retrieval test"
        assert result.metadata == {"key": "val"}

    @pytest.mark.asyncio
    async def test_health_check_markdown(self, tmp_path: Any) -> None:
        """health_check() returns dict with status='ok' in markdown mode."""
        mem_dir = tmp_path / "memories"
        mem = FileMemory(mem_dir, format="markdown")
        result = await mem.health_check()
        assert isinstance(result, dict)
        assert result.get("status") == "ok"

    @pytest.mark.asyncio
    async def test_markdown_file_format(self, tmp_path: Any) -> None:
        """Markdown files have correct structure (title + content + metadata comment)."""
        mem_dir = tmp_path / "memories"
        mem = FileMemory(mem_dir, format="markdown")
        await mem.store("first line of content\ncontinued", {"tag": "test"})

        md_files = list(mem_dir.glob("*.md"))
        assert len(md_files) == 1
        content = md_files[0].read_text()
        assert "# first line of content" in content
        assert "<!-- metadata:" in content

    @pytest.mark.asyncio
    async def test_parent_dirs_created_markdown(self, tmp_path: Any) -> None:
        """Markdown mode creates parent dirs automatically."""
        mem_dir = tmp_path / "x" / "y" / "z"
        mem = FileMemory(mem_dir, format="markdown")
        await mem.store("nested test", {})
        assert mem_dir.is_dir()
        assert await mem.count() == 1

"""Tests for the expanded native memory tool family."""

from __future__ import annotations

from pathlib import Path

import pytest

from sage.agent import Agent
from sage.memory.file_backend import FileMemory
from sage.models import ToolResult


def _make_agent_with_memory(tmp_path: Path) -> Agent:
    memory = FileMemory(tmp_path / "mem.json", format="json")
    agent = Agent(name="memory-agent", model="gpt-4o-mini", memory=memory)
    agent._register_memory_tools()
    return agent


class TestMemoryToolRegistration:
    def test_expanded_memory_tools_registered_when_memory_configured(self, tmp_path: Path) -> None:
        agent = _make_agent_with_memory(tmp_path)
        tool_names = {schema.name for schema in agent.tool_registry.get_schemas()}
        assert "memory_add" in tool_names
        assert "memory_search" in tool_names
        assert "memory_get" in tool_names
        assert "memory_list" in tool_names
        assert "memory_delete" in tool_names
        assert "memory_stats" in tool_names

    def test_memory_tools_expose_stateful_metadata(self, tmp_path: Path) -> None:
        agent = _make_agent_with_memory(tmp_path)
        schemas = {schema.name: schema for schema in agent.tool_registry.get_schemas()}
        assert schemas["memory_add"].metadata is not None
        assert schemas["memory_add"].metadata.resource_kind == "memory"
        assert schemas["memory_add"].metadata.stateful is True


class TestMemoryToolBehavior:
    @pytest.mark.asyncio
    async def test_memory_add_returns_id(self, tmp_path: Path) -> None:
        agent = _make_agent_with_memory(tmp_path)

        result = await agent.tool_registry.execute_result(
            "memory_add",
            {"content": "alpha note", "metadata": {"topic": "project"}},
        )

        assert isinstance(result, ToolResult)
        assert result.resource is not None
        assert result.resource.kind == "memory"
        assert result.metadata["memory_id"] == result.resource.resource_id

    @pytest.mark.asyncio
    async def test_memory_search_returns_ranked_entries(self, tmp_path: Path) -> None:
        agent = _make_agent_with_memory(tmp_path)
        await agent.tool_registry.execute_result("memory_add", {"content": "apollo roadmap"})
        await agent.tool_registry.execute_result("memory_add", {"content": "grocery list"})

        result = await agent.tool_registry.execute_result(
            "memory_search",
            {"query": "apollo", "limit": 5},
        )

        assert result.data is not None
        assert result.data["count"] == 1
        assert result.data["entries"][0]["content"] == "apollo roadmap"

    @pytest.mark.asyncio
    async def test_memory_get_returns_single_entry(self, tmp_path: Path) -> None:
        agent = _make_agent_with_memory(tmp_path)
        created = await agent.tool_registry.execute_result(
            "memory_add",
            {"content": "retrieve me"},
        )

        result = await agent.tool_registry.execute_result(
            "memory_get",
            {"memory_id": created.resource.resource_id},
        )

        assert result.data is not None
        assert result.data["entry"]["content"] == "retrieve me"

    @pytest.mark.asyncio
    async def test_memory_list_paginates(self, tmp_path: Path) -> None:
        agent = _make_agent_with_memory(tmp_path)
        await agent.tool_registry.execute_result("memory_add", {"content": "one"})
        await agent.tool_registry.execute_result("memory_add", {"content": "two"})
        await agent.tool_registry.execute_result("memory_add", {"content": "three"})

        result = await agent.tool_registry.execute_result(
            "memory_list",
            {"limit": 2, "offset": 1},
        )

        assert result.data is not None
        assert result.data["count"] == 2
        assert len(result.data["entries"]) == 2

    @pytest.mark.asyncio
    async def test_memory_delete_removes_record(self, tmp_path: Path) -> None:
        agent = _make_agent_with_memory(tmp_path)
        created = await agent.tool_registry.execute_result(
            "memory_add",
            {"content": "delete me"},
        )

        deleted = await agent.tool_registry.execute_result(
            "memory_delete",
            {"memory_id": created.resource.resource_id},
        )
        remaining = await agent.tool_registry.execute_result("memory_stats", {})

        assert deleted.data is not None
        assert deleted.data["deleted"] is True
        assert remaining.data is not None
        assert remaining.data["count"] == 0

    @pytest.mark.asyncio
    async def test_memory_stats_returns_backend_status(self, tmp_path: Path) -> None:
        agent = _make_agent_with_memory(tmp_path)
        await agent.tool_registry.execute_result("memory_add", {"content": "status check"})

        result = await agent.tool_registry.execute_result("memory_stats", {})

        assert result.data is not None
        assert result.data["status"] == "ok"
        assert result.data["count"] == 1
        assert result.data["backend"] == "file"

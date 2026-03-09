"""Tests for persistent process tools."""

from __future__ import annotations

import sys

import pytest

from sage.tools.process_tools import (
    process_kill,
    process_read,
    process_send,
    process_start,
    process_wait,
)
from sage.tools.registry import ToolRegistry


class TestProcessTools:
    @pytest.mark.asyncio
    async def test_process_start_and_wait(self) -> None:
        started = await process_start([sys.executable, "-c", "print('hi')"])
        process_id = started.resource.resource_id

        waited = await process_wait(process_id, timeout=1.0)

        assert waited.data is not None
        assert waited.data["returncode"] == 0
        assert waited.data["running"] is False

    @pytest.mark.asyncio
    async def test_process_send_and_read(self) -> None:
        started = await process_start(
            [
                sys.executable,
                "-c",
                "import sys; data = sys.stdin.readline().strip(); print(data.upper())",
            ]
        )
        process_id = started.resource.resource_id

        await process_send(process_id, "hello\n")
        await process_wait(process_id, timeout=1.0)
        read = await process_read(process_id, max_chars=1000)

        assert read.data is not None
        assert "HELLO" in read.data["output"]

    @pytest.mark.asyncio
    async def test_process_kill_terminates_running_process(self) -> None:
        started = await process_start(
            [sys.executable, "-c", "import time; time.sleep(30)"]
        )
        process_id = started.resource.resource_id

        killed = await process_kill(process_id)

        assert killed.data is not None
        assert killed.data["running"] is False


class TestProcessToolMetadata:
    def test_process_tools_expose_process_metadata(self) -> None:
        assert process_start.__tool_schema__.metadata is not None
        assert process_start.__tool_schema__.metadata.resource_kind == "process"
        assert process_start.__tool_schema__.metadata.stateful is True


class TestProcessPermissionLoading:
    def test_register_from_permissions_loads_process_tools(self) -> None:
        from sage.config import Permission

        registry = ToolRegistry()
        registry.register_from_permissions(Permission(process="allow"))

        tool_names = {schema.name for schema in registry.get_schemas()}
        assert "process_start" in tool_names
        assert "process_wait" in tool_names

"""Tests for ToolRegistry."""

from __future__ import annotations

import asyncio
import logging
import sys
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from sage.config import Permission
from sage.exceptions import ToolError
from sage.models import ToolSchema
from sage.tools.base import ToolBase
from sage.tools.decorator import tool
from sage.tools.registry import ToolRegistry


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool
async def async_greet(name: str) -> str:
    """Greet someone asynchronously."""
    return f"Hello, {name}!"


class MathTool(ToolBase):
    @tool
    def multiply(self, x: int, y: int) -> int:
        """Multiply two numbers."""
        return x * y


class TestToolRegistry:
    """Tests for registration and execution."""

    def test_register_and_get_schemas(self) -> None:
        registry = ToolRegistry()
        registry.register(add)
        schemas = registry.get_schemas()
        assert len(schemas) == 1
        assert schemas[0].name == "add"

    async def test_execute_sync_function(self) -> None:
        registry = ToolRegistry()
        registry.register(add)
        result = await registry.execute("add", {"a": 2, "b": 3})
        assert result == "5"

    async def test_execute_async_function(self) -> None:
        registry = ToolRegistry()
        registry.register(async_greet)
        result = await registry.execute("async_greet", {"name": "World"})
        assert result == "Hello, World!"

    async def test_execute_unknown_tool_raises(self) -> None:
        registry = ToolRegistry()
        with pytest.raises(ToolError, match="Unknown tool"):
            await registry.execute("nonexistent", {})

    def test_register_invalid_raises(self) -> None:
        registry = ToolRegistry()
        with pytest.raises(ToolError, match="Cannot register"):
            registry.register(lambda: None)  # type: ignore[arg-type]

    def test_register_toolbase_instance(self) -> None:
        registry = ToolRegistry()
        math_tool = MathTool()
        registry.register(math_tool)
        schemas = registry.get_schemas()
        assert len(schemas) == 1
        assert schemas[0].name == "multiply"

    async def test_execute_toolbase_method(self) -> None:
        registry = ToolRegistry()
        math_tool = MathTool()
        registry.register(math_tool)
        result = await registry.execute("multiply", {"x": 3, "y": 4})
        assert result == "12"

    def test_load_from_module(self, tmp_path: Path) -> None:
        """Load tools from a dynamically created module."""
        mod_file = tmp_path / "sample_tools.py"
        mod_file.write_text(
            textwrap.dedent("""\
                from sage.tools.decorator import tool

                @tool
                def sample_add(a: int, b: int) -> int:
                    \"\"\"Add two numbers.\"\"\"
                    return a + b
            """)
        )

        # Add tmp_path to sys.path so importlib can find it.
        sys.path.insert(0, str(tmp_path))
        try:
            registry = ToolRegistry()
            registry.load_from_module("sample_tools")
            schemas = registry.get_schemas()
            assert any(s.name == "sample_add" for s in schemas)
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("sample_tools", None)

    def test_load_from_module_with_attr(self, tmp_path: Path) -> None:
        """Load a specific tool from a module using colon syntax."""
        mod_file = tmp_path / "specific_tools.py"
        mod_file.write_text(
            textwrap.dedent("""\
                from sage.tools.decorator import tool

                @tool
                def wanted(x: str) -> str:
                    \"\"\"Wanted tool.\"\"\"
                    return x

                @tool
                def unwanted(x: str) -> str:
                    \"\"\"Unwanted tool.\"\"\"
                    return x
            """)
        )

        sys.path.insert(0, str(tmp_path))
        try:
            registry = ToolRegistry()
            registry.load_from_module("specific_tools:wanted")
            schemas = registry.get_schemas()
            assert len(schemas) == 1
            assert schemas[0].name == "wanted"
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("specific_tools", None)

    def test_multiple_registrations(self) -> None:
        registry = ToolRegistry()
        registry.register(add)
        registry.register(async_greet)
        schemas = registry.get_schemas()
        assert len(schemas) == 2
        names = {s.name for s in schemas}
        assert names == {"add", "async_greet"}

    async def test_execute_tool_that_raises(self) -> None:
        @tool
        def failing(x: int) -> int:
            """Always fails."""
            raise ValueError("boom")

        registry = ToolRegistry()
        registry.register(failing)
        with pytest.raises(ToolError, match="Tool 'failing' failed"):
            await registry.execute("failing", {"x": 1})


class TestToolRegistryLogging:
    async def test_execute_logs_dispatch(self, caplog: pytest.LogCaptureFixture) -> None:
        """ToolRegistry.execute should log DEBUG with the tool name."""

        @tool
        def greet(name: str) -> str:
            """Greet someone."""
            return f"Hello, {name}!"

        registry = ToolRegistry()
        registry.register(greet)

        with caplog.at_level(logging.DEBUG, logger="sage.tools.registry"):
            await registry.execute("greet", {"name": "world"})

        all_messages = " ".join(r.message for r in caplog.records)
        assert "greet" in all_messages, f"Expected tool name in logs, got: {all_messages}"


class TestBuiltinNameResolution:
    """Tests for bare built-in name auto-resolution (no prefix required)."""

    def test_bare_shell_loads_builtin(self) -> None:
        registry = ToolRegistry()
        registry.load_from_module("shell")
        names = {s.name for s in registry.get_schemas()}
        assert "shell" in names

    def test_bare_file_read_loads_builtin(self) -> None:
        registry = ToolRegistry()
        registry.load_from_module("file_read")
        names = {s.name for s in registry.get_schemas()}
        assert "file_read" in names

    def test_bare_http_request_loads_builtin(self) -> None:
        registry = ToolRegistry()
        registry.load_from_module("http_request")
        names = {s.name for s in registry.get_schemas()}
        assert "http_request" in names

    def test_bare_memory_store_loads_builtin(self) -> None:
        registry = ToolRegistry()
        registry.load_from_module("memory_store")
        names = {s.name for s in registry.get_schemas()}
        assert "memory_store" in names

    def test_bare_memory_recall_loads_builtin(self) -> None:
        registry = ToolRegistry()
        registry.load_from_module("memory_recall")
        names = {s.name for s in registry.get_schemas()}
        assert "memory_recall" in names

    def test_legacy_builtin_prefix_still_works(self) -> None:
        """builtin: prefix is still accepted for backwards compatibility."""
        registry = ToolRegistry()
        registry.load_from_module("builtin:shell")
        names = {s.name for s in registry.get_schemas()}
        assert "shell" in names

    def test_legacy_builtin_all_still_works(self) -> None:
        """'builtin' (without colon) loads all built-in tools."""
        registry = ToolRegistry()
        registry.load_from_module("builtin")
        names = {s.name for s in registry.get_schemas()}
        assert {
            "shell",
            "file_read",
            "file_write",
            "http_request",
            "memory_store",
            "memory_recall",
        }.issubset(names)


class TestMCPToolRegistration:
    """Tests for register_mcp_tool and MCP-backed tool dispatch."""

    async def test_register_mcp_tool_schema_visible(self) -> None:
        """Registered MCP tool schema appears in get_schemas()."""
        from unittest.mock import AsyncMock

        registry = ToolRegistry()
        schema = ToolSchema(
            name="mcp_read",
            description="Read a file via MCP",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        )
        client = AsyncMock()
        registry.register_mcp_tool(schema, client)

        schemas = registry.get_schemas()
        assert any(s.name == "mcp_read" for s in schemas)

    async def test_execute_routes_to_mcp_client(self) -> None:
        """execute() for an MCP tool calls client.call_tool with name and args."""
        from unittest.mock import AsyncMock

        registry = ToolRegistry()
        schema = ToolSchema(
            name="list_files",
            description="List files",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        )
        client = AsyncMock()
        client.call_tool = AsyncMock(return_value="file1.txt\nfile2.txt")
        registry.register_mcp_tool(schema, client)

        result = await registry.execute("list_files", {"path": "/tmp"})

        client.call_tool.assert_awaited_once_with("list_files", {"path": "/tmp"})
        assert result == "file1.txt\nfile2.txt"

    async def test_local_tool_not_overshadowed_by_mcp(self) -> None:
        """A local @tool is still callable when MCP tools are also registered."""
        from unittest.mock import AsyncMock

        registry = ToolRegistry()
        registry.register(add)

        mcp_schema = ToolSchema(name="other_tool", description="MCP tool", parameters={})
        client = AsyncMock()
        client.call_tool = AsyncMock(return_value="mcp_result")
        registry.register_mcp_tool(mcp_schema, client)

        # Local tool still dispatches normally.
        local_result = await registry.execute("add", {"a": 10, "b": 5})
        assert local_result == "15"

        # MCP tool dispatches through client.
        mcp_result = await registry.execute("other_tool", {})
        assert mcp_result == "mcp_result"


class TestToolRegistryPermissions:
    """Tests for permission checks in execute()."""

    async def test_allow_permission_executes_tool(self) -> None:
        from sage.permissions.base import PermissionAction, PermissionDecision

        handler = AsyncMock()
        handler.check = AsyncMock(return_value=PermissionDecision(action=PermissionAction.ALLOW))

        registry = ToolRegistry()
        registry.set_permission_handler(handler)
        registry.register(add)

        result = await registry.execute("add", {"a": 1, "b": 2})
        assert result == "3"
        handler.check.assert_awaited_once_with("add", {"a": 1, "b": 2})

    async def test_deny_permission_raises(self) -> None:
        from sage.exceptions import PermissionError as SagePermissionError
        from sage.permissions.base import PermissionAction, PermissionDecision

        handler = AsyncMock()
        handler.check = AsyncMock(
            return_value=PermissionDecision(action=PermissionAction.DENY, reason="blocked")
        )

        registry = ToolRegistry()
        registry.set_permission_handler(handler)
        registry.register(add)

        with pytest.raises(SagePermissionError, match="Permission denied"):
            await registry.execute("add", {"a": 1, "b": 2})

    async def test_ask_permission_raises_no_interactive_handler(self) -> None:
        """ASK action with no interactive handler must raise SagePermissionError."""
        from sage.exceptions import PermissionError as SagePermissionError
        from sage.permissions.base import PermissionAction, PermissionDecision

        handler = AsyncMock()
        handler.check = AsyncMock(return_value=PermissionDecision(action=PermissionAction.ASK))

        registry = ToolRegistry()
        registry.set_permission_handler(handler)
        registry.register(add)

        with pytest.raises(SagePermissionError, match="no interactive handler"):
            await registry.execute("add", {"a": 1, "b": 2})

    async def test_no_handler_allows_execution(self) -> None:
        """Without a permission handler, tools execute normally."""
        registry = ToolRegistry()
        registry.register(add)
        result = await registry.execute("add", {"a": 5, "b": 5})
        assert result == "10"


class TestNewToolBarenames:
    """Tests for new tool bareword resolution."""

    def test_file_edit_loads(self) -> None:
        registry = ToolRegistry()
        registry.load_from_module("file_edit")
        names = {s.name for s in registry.get_schemas()}
        assert "file_edit" in names

    @pytest.mark.parametrize(
        "name",
        ["web_search", "web_fetch"],
    )
    def test_web_tools_load(self, name: str) -> None:
        registry = ToolRegistry()
        registry.load_from_module(name)
        names = {s.name for s in registry.get_schemas()}
        assert name in names


class TestRegisterFromPermissions:
    def test_register_from_permissions_allow(self) -> None:
        registry = ToolRegistry()

        registry.register_from_permissions(Permission(shell="allow"))

        names = {s.name for s in registry.get_schemas()}
        assert "shell" in names

    def test_register_from_permissions_deny(self) -> None:
        registry = ToolRegistry()

        registry.register_from_permissions(Permission(shell="deny"))

        names = {s.name for s in registry.get_schemas()}
        assert "shell" not in names

    def test_register_from_permissions_pattern_dict_registers(self) -> None:
        registry = ToolRegistry()

        registry.register_from_permissions(Permission(shell={"*": "ask"}))

        names = {s.name for s in registry.get_schemas()}
        assert "shell" in names

    def test_register_from_permissions_default_ask_registers(self) -> None:
        registry = ToolRegistry()

        registry.register_from_permissions(Permission(), default="ask")

        names = {s.name for s in registry.get_schemas()}
        assert {
            "file_read",
            "file_write",
            "file_edit",
            "shell",
            "http_request",
            "web_fetch",
            "web_search",
            "memory_store",
            "memory_recall",
        }.issubset(names)

    def test_register_from_permissions_extensions(self) -> None:
        registry = ToolRegistry()

        registry.register_from_permissions(
            Permission(read="deny", edit="deny", shell="deny", web="deny", memory="deny"),
            default="deny",
            extensions=["sage.tools.file_tools"],
        )

        names = {s.name for s in registry.get_schemas()}
        assert "file_edit" in names


class TestToolModuleMap:
    def test_tool_module_map_no_git_tools(self) -> None:
        assert "git_status" not in ToolRegistry._TOOL_MODULE_MAP
        assert "git_diff" not in ToolRegistry._TOOL_MODULE_MAP
        assert "git_log" not in ToolRegistry._TOOL_MODULE_MAP
        assert "git_checkout" not in ToolRegistry._TOOL_MODULE_MAP
        assert "git_commit" not in ToolRegistry._TOOL_MODULE_MAP
        assert "git_pr_create" not in ToolRegistry._TOOL_MODULE_MAP

    def test_tool_module_map_no_glob_grep(self) -> None:
        assert "glob_find" not in ToolRegistry._TOOL_MODULE_MAP
        assert "grep_search" not in ToolRegistry._TOOL_MODULE_MAP


class TestGitCategory:
    def test_git_category_exists(self) -> None:
        from sage.tools.registry import CATEGORY_TOOLS

        assert "git" in CATEGORY_TOOLS

    def test_git_category_tools_listed(self) -> None:
        from sage.tools.registry import CATEGORY_TOOLS

        git_tools = CATEGORY_TOOLS["git"]
        assert "git_status" in git_tools
        assert "git_diff" in git_tools
        assert "git_log" in git_tools
        assert "git_commit" in git_tools
        assert "git_branch" in git_tools
        assert "git_undo" in git_tools
        assert "snapshot_create" in git_tools
        assert "snapshot_restore" in git_tools
        assert "snapshot_list" in git_tools

    def test_git_category_arg_map_is_none(self) -> None:
        from sage.tools.registry import CATEGORY_ARG_MAP

        assert CATEGORY_ARG_MAP["git"] is None


class TestToolTimeout:
    """Tests for per-tool and registry-default timeouts."""

    async def test_tool_times_out(self) -> None:
        """Tool that runs too long raises ToolError."""

        @tool
        async def slow_tool(x: str) -> str:
            """Slow tool."""
            await asyncio.sleep(10)
            return x

        registry = ToolRegistry(default_timeout=0.05)
        registry.register(slow_tool)
        with pytest.raises(ToolError, match="timed out"):
            await registry.execute("slow_tool", {"x": "hi"})

    async def test_per_tool_timeout_overrides_default(self) -> None:
        """Per-tool timeout takes precedence over registry default."""

        @tool(timeout=0.05)
        async def fast_timeout_tool(x: str) -> str:
            """Fast timeout tool."""
            await asyncio.sleep(10)
            return x

        registry = ToolRegistry(default_timeout=60.0)  # high default
        registry.register(fast_timeout_tool)
        with pytest.raises(ToolError, match="timed out"):
            await registry.execute("fast_timeout_tool", {"x": "hi"})

    async def test_no_timeout_when_not_set(self) -> None:
        """Tool completes normally when no timeout."""

        @tool
        async def quick_tool(x: str) -> str:
            """Quick tool."""
            return f"done:{x}"

        registry = ToolRegistry()
        registry.register(quick_tool)
        result = await registry.execute("quick_tool", {"x": "test"})
        assert result == "done:test"

    async def test_tool_decorator_stores_timeout(self) -> None:
        """@tool(timeout=30) stores __tool_timeout__ on the function."""

        @tool(timeout=30.0)
        def my_tool(x: str) -> str:
            """A tool."""
            return x

        assert hasattr(my_tool, "__tool_timeout__")
        assert my_tool.__tool_timeout__ == 30.0

    async def test_plain_tool_decorator_no_timeout(self) -> None:
        """@tool (no args) does not set __tool_timeout__."""

        @tool
        def my_tool(x: str) -> str:
            """A tool."""
            return x

        assert not hasattr(my_tool, "__tool_timeout__")

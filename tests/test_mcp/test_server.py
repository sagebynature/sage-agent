"""Tests for the MCP server."""

from __future__ import annotations

import pytest

from sage.mcp.server import MCPServer
from sage.tools.decorator import tool
from sage.tools.registry import ToolRegistry


@tool
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"


@tool
def add(a: int, b: int) -> str:
    """Add two numbers."""
    return str(a + b)


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(greet)
    reg.register(add)
    return reg


class TestMCPServerInit:
    def test_creates_server(self, registry: ToolRegistry) -> None:
        server = MCPServer("test-server", registry)
        assert server._name == "test-server"
        assert server._registry is registry
        assert server._server is not None

    def test_server_has_handlers(self, registry: ToolRegistry) -> None:
        server = MCPServer("test-server", registry)
        # The server should have been set up with handlers
        assert server._server is not None

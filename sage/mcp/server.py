"""Expose agent tools as an MCP server."""

from __future__ import annotations

from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from sage.tools.registry import ToolRegistry


class MCPServer:
    """Expose a ToolRegistry as an MCP server."""

    def __init__(self, name: str, registry: ToolRegistry) -> None:
        self._name = name
        self._registry = registry
        self._server = Server(name)
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        @self._server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
        async def list_tools() -> list[Tool]:
            schemas = self._registry.get_schemas()
            return [
                Tool(
                    name=s.name,
                    description=s.description,
                    inputSchema=s.parameters,
                )
                for s in schemas
            ]

        @self._server.call_tool()  # type: ignore[untyped-decorator]
        async def call_tool(
            name: str, arguments: dict[str, Any] | None = None
        ) -> list[TextContent]:
            result = await self._registry.execute(name, arguments or {})
            return [TextContent(type="text", text=str(result))]

    async def serve_stdio(self) -> None:
        """Start serving via stdio transport."""
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream,
                write_stream,
                self._server.create_initialization_options(),
            )

"""MCP client for connecting to MCP servers and discovering/calling tools."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any

import anyio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from sage.exceptions import SageError
from sage.models import ToolSchema

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for connecting to MCP servers."""

    def __init__(
        self,
        transport: str = "stdio",
        command: str | None = None,
        url: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._transport = transport
        self._command = command
        self._url = url
        self._args = args or []
        self._env = env or {}
        self._session: ClientSession | None = None
        self._exit_stack = AsyncExitStack()

    async def connect(self) -> None:
        """Establish connection to the MCP server."""
        logger.info("MCP connecting: transport=%s", self._transport)
        try:
            if self._transport == "stdio":
                if not self._command:
                    raise SageError("Command required for stdio transport")
                server_params = StdioServerParameters(
                    command=self._command,
                    args=self._args,
                    env=self._env or None,
                )
                stdio_transport = await self._exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                read_stream, write_stream = stdio_transport
                self._session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
            elif self._transport == "sse":
                from mcp.client.sse import sse_client

                if not self._url:
                    raise SageError("URL required for SSE transport")
                sse_transport = await self._exit_stack.enter_async_context(sse_client(self._url))
                read_stream, write_stream = sse_transport
                self._session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
            else:
                raise SageError(f"Unsupported transport: {self._transport}")

            await self._session.initialize()
            logger.info("MCP connected: transport=%s", self._transport)
        except SageError:
            raise
        except Exception as exc:
            logger.error("MCP connection failed: %s", exc)
            raise SageError(f"Failed to connect to MCP server: {exc}") from exc

    async def discover_tools(self) -> list[ToolSchema]:
        """Get available tools from the connected MCP server."""
        if not self._session:
            raise SageError("Not connected. Call connect() first.")

        result = await self._session.list_tools()
        schemas: list[ToolSchema] = []
        for tool in result.tools:
            schemas.append(
                ToolSchema(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=tool.inputSchema if hasattr(tool, "inputSchema") else {},
                )
            )
        return schemas

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Execute a tool on the MCP server."""
        if not self._session:
            raise SageError("Not connected. Call connect() first.")
        logger.debug("MCP call_tool: %s", name)

        result = await self._session.call_tool(name, arguments=arguments or {})

        parts: list[str] = []
        for content in result.content:
            if hasattr(content, "text"):
                parts.append(content.text)
            else:
                parts.append(str(content))
        return "\n".join(parts)

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        logger.debug("MCP disconnecting")
        try:
            await self._exit_stack.aclose()
        except (asyncio.CancelledError, anyio.get_cancelled_exc_class()):
            logger.debug("MCP disconnect: subprocess cleanup cancelled (safe to ignore)")
        except RuntimeError as exc:
            # anyio raises RuntimeError("Attempted to exit cancel scope in a
            # different task than it was entered in") when the stdio_client
            # async generator is torn down from a different asyncio Task than
            # the one that opened it.  This is cosmetic cleanup noise — the
            # subprocess has already exited.
            logger.debug("MCP disconnect: cancel-scope mismatch (safe to ignore): %s", exc)
        self._session = None

    @property
    def is_connected(self) -> bool:
        """Whether the client is currently connected."""
        return self._session is not None

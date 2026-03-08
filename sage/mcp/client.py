"""MCP client for connecting to MCP servers and discovering/calling tools."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any

import anyio

from mcp import ClientSession, StdioServerParameters  # type: ignore[import-not-found]
from mcp.client.stdio import stdio_client  # type: ignore[import-not-found]

from sage.exceptions import SageError
from sage.models import ToolSchema

logger = logging.getLogger(__name__)


def _install_mcp_asyncgen_error_suppressor() -> None:
    """Install a targeted event loop exception handler that silences the
    ``RuntimeError("Attempted to exit cancel scope in a different task…")``
    that asyncio's ``shutdown_asyncgens()`` logs when it finalizes a
    ``stdio_client`` generator that failed to close cleanly.

    The handler is idempotent (installed at most once per loop) and only
    suppresses the specific ``"closing of asynchronous generator"`` messages
    whose exception mentions ``"cancel scope"``.  All other exceptions are
    forwarded to the original handler.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # no running loop — nothing to install

    existing = loop.get_exception_handler()
    if getattr(existing, "_mcp_cancel_scope_suppressor", False):
        return  # already installed

    def _handler(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        exc = context.get("exception")
        msg = context.get("message", "")
        if (
            "closing of asynchronous generator" in msg
            and isinstance(exc, RuntimeError)
            and "cancel scope" in str(exc)
        ):
            logger.debug("MCP asyncgen finalization suppressed: %s", exc)
            return
        if existing is not None:
            existing(loop, context)
        else:
            loop.default_exception_handler(context)

    _handler._mcp_cancel_scope_suppressor = True  # type: ignore[attr-defined]
    loop.set_exception_handler(_handler)


class MCPClient:
    """Client for connecting to MCP servers."""

    def __init__(
        self,
        transport: str = "stdio",
        command: str | None = None,
        url: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        initialize_timeout: float = 10.0,
    ) -> None:
        self._transport = transport
        self._command = command
        self._url = url
        self._args = args or []
        self._env = env or {}
        self._initialize_timeout = initialize_timeout
        self._session: ClientSession | None = None
        self._exit_stack = AsyncExitStack()

    async def connect(self) -> None:
        """Establish connection to the MCP server."""
        logger.debug("MCP connecting: transport=%s", self._transport)
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
                from mcp.client.sse import sse_client  # type: ignore[import-not-found]

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
            logger.debug("MCP connected: transport=%s", self._transport)
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
            # async generator is torn down from a different asyncio Task.
            # The generator remains open and asyncio's shutdown_asyncgens()
            # will try to finalize it later — install a targeted handler to
            # silence that follow-on error too.
            logger.debug("MCP disconnect: cancel-scope mismatch (safe to ignore): %s", exc)
            _install_mcp_asyncgen_error_suppressor()
        self._session = None

    @property
    def is_connected(self) -> bool:
        """Whether the client is currently connected."""
        return self._session is not None

    @property
    def initialize_timeout(self) -> float:
        """Maximum time allowed for connect/discovery during agent startup."""
        return self._initialize_timeout

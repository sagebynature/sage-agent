"""Tests for the MCP client."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from sage.exceptions import SageError
from sage.mcp.client import MCPClient


@pytest.fixture
def stdio_client_instance() -> MCPClient:
    return MCPClient(server_name="stdio-test", transport="stdio", command="echo", args=["hello"])


@pytest.fixture
def sse_client_instance() -> MCPClient:
    return MCPClient(server_name="sse-test", transport="sse", url="http://localhost:8080/sse")


class TestMCPClientInit:
    def test_stdio_params(self, stdio_client_instance: MCPClient) -> None:
        assert stdio_client_instance.server_name == "stdio-test"
        assert stdio_client_instance._transport == "stdio"
        assert stdio_client_instance._command == "echo"
        assert stdio_client_instance._args == ["hello"]
        assert not stdio_client_instance.is_connected

    def test_sse_params(self, sse_client_instance: MCPClient) -> None:
        assert sse_client_instance.server_name == "sse-test"
        assert sse_client_instance._transport == "sse"
        assert sse_client_instance._url == "http://localhost:8080/sse"
        assert not sse_client_instance.is_connected

    def test_default_transport(self) -> None:
        client = MCPClient(server_name="default")
        assert client._transport == "stdio"


class TestMCPClientNotConnected:
    async def test_discover_tools_raises_when_not_connected(
        self, stdio_client_instance: MCPClient
    ) -> None:
        with pytest.raises(SageError, match="Not connected"):
            await stdio_client_instance.discover_tools()

    async def test_call_tool_raises_when_not_connected(
        self, stdio_client_instance: MCPClient
    ) -> None:
        with pytest.raises(SageError, match="Not connected"):
            await stdio_client_instance.call_tool("test")


class TestMCPClientConnectErrors:
    async def test_stdio_missing_command_raises(self) -> None:
        client = MCPClient(transport="stdio")
        with pytest.raises(SageError, match="Command required"):
            await client.connect()

    async def test_sse_missing_url_raises(self) -> None:
        client = MCPClient(transport="sse")
        with pytest.raises(SageError, match="URL required"):
            await client.connect()

    async def test_unsupported_transport_raises(self) -> None:
        client = MCPClient(transport="websocket")
        with pytest.raises(SageError, match="Unsupported transport"):
            await client.connect()


class TestMCPClientWithMockSession:
    async def test_discover_tools(self, stdio_client_instance: MCPClient) -> None:
        mock_session = AsyncMock()
        mock_tool = SimpleNamespace(
            name="test_tool",
            description="A test tool",
            inputSchema={"type": "object", "properties": {"x": {"type": "string"}}},
        )
        mock_session.list_tools = AsyncMock(return_value=SimpleNamespace(tools=[mock_tool]))
        stdio_client_instance._session = mock_session

        schemas = await stdio_client_instance.discover_tools()

        assert len(schemas) == 1
        assert schemas[0].name == "test_tool"
        assert schemas[0].description == "A test tool"
        assert schemas[0].parameters == {"type": "object", "properties": {"x": {"type": "string"}}}

    async def test_call_tool(self, stdio_client_instance: MCPClient) -> None:
        mock_session = AsyncMock()
        mock_content = SimpleNamespace(text="result text")
        mock_session.call_tool = AsyncMock(return_value=SimpleNamespace(content=[mock_content]))
        stdio_client_instance._session = mock_session

        result = await stdio_client_instance.call_tool("test_tool", {"x": "hello"})

        assert result == "result text"
        mock_session.call_tool.assert_called_once_with("test_tool", arguments={"x": "hello"})

    async def test_call_tool_empty_args(self, stdio_client_instance: MCPClient) -> None:
        mock_session = AsyncMock()
        mock_content = SimpleNamespace(text="ok")
        mock_session.call_tool = AsyncMock(return_value=SimpleNamespace(content=[mock_content]))
        stdio_client_instance._session = mock_session

        await stdio_client_instance.call_tool("test_tool")

        mock_session.call_tool.assert_called_once_with("test_tool", arguments={})

    async def test_disconnect_clears_session(self, stdio_client_instance: MCPClient) -> None:
        stdio_client_instance._session = AsyncMock()
        stdio_client_instance._exit_stack = AsyncMock()

        await stdio_client_instance.disconnect()

        assert stdio_client_instance._session is None

    async def test_is_connected_true(self, stdio_client_instance: MCPClient) -> None:
        stdio_client_instance._session = AsyncMock()
        assert stdio_client_instance.is_connected

    async def test_discover_multiple_tools(self, stdio_client_instance: MCPClient) -> None:
        mock_session = AsyncMock()
        tools = [
            SimpleNamespace(name="tool_a", description="Tool A", inputSchema={}),
            SimpleNamespace(name="tool_b", description="Tool B", inputSchema={}),
        ]
        mock_session.list_tools = AsyncMock(return_value=SimpleNamespace(tools=tools))
        stdio_client_instance._session = mock_session

        schemas = await stdio_client_instance.discover_tools()

        assert len(schemas) == 2
        assert schemas[0].name == "tool_a"
        assert schemas[1].name == "tool_b"


class TestMCPClientLogging:
    async def test_call_tool_logs_debug(
        self,
        stdio_client_instance: MCPClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_session = AsyncMock()
        mock_content = SimpleNamespace(text="result")
        mock_session.call_tool = AsyncMock(return_value=SimpleNamespace(content=[mock_content]))
        stdio_client_instance._session = mock_session

        with caplog.at_level(logging.DEBUG, logger="sage.mcp.client"):
            await stdio_client_instance.call_tool("my_tool", {"x": "1"})

        assert any("my_tool" in r.message for r in caplog.records)

    async def test_disconnect_logs_debug(
        self,
        stdio_client_instance: MCPClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        stdio_client_instance._session = AsyncMock()
        stdio_client_instance._exit_stack = AsyncMock()

        with caplog.at_level(logging.DEBUG, logger="sage.mcp.client"):
            await stdio_client_instance.disconnect()

        assert any("disconnect" in r.message.lower() for r in caplog.records)

"""JSON-RPC server for sage serve command."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


class JsonRpcServer:
    """JSON-RPC 2.0 server over stdin/stdout."""

    def __init__(self, agent_config: str | None = None, verbose: bool = False) -> None:
        """Initialize the JSON-RPC server.

        Args:
            agent_config: Path to agent configuration file (optional).
            verbose: Enable verbose logging.
        """
        self.agent_config = agent_config
        self.verbose = verbose
        self._should_shutdown = False
        self._dispatcher: Any | None = None

    def set_dispatcher(self, dispatcher: Any) -> None:
        self._dispatcher = dispatcher

    async def start(self) -> None:
        """Start the JSON-RPC server and process incoming requests.

        Main read loop that:
        1. Reads JSON-RPC messages from stdin
        2. Routes to appropriate handler
        3. Sends responses back to stdout
        """
        while not self._should_shutdown:
            try:
                line = await self._read_line()

                if line is None:
                    break

                message = self._parse_json(line)
                if message is None:
                    continue

                response = await self._handle_request(message)

                if response is not None:
                    await self._write_response(response)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message loop: {e}")
                break

        await self.shutdown()

    async def _read_line(self) -> str | None:
        """Read a single line from stdin in a non-blocking way."""
        loop = asyncio.get_event_loop()
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            return line if line else None
        except Exception as e:
            logger.error(f"Error reading from stdin: {e}")
            return None

    def _parse_json(self, line: str) -> dict | None:
        """Parse a JSON line, logging warnings on error."""
        if not line or not line.strip():
            return None

        try:
            return json.loads(line)
        except json.JSONDecodeError as e:
            logger.warning(f"Malformed JSON received: {e}")
            return None

    async def _write_response(self, response: dict) -> None:
        """Write a JSON response to stdout."""
        loop = asyncio.get_event_loop()
        try:
            json_str = json.dumps(response)
            await loop.run_in_executor(None, sys.stdout.write, json_str + "\n")
            await loop.run_in_executor(None, sys.stdout.flush)
        except Exception as e:
            logger.error(f"Error writing message: {e}")

    async def _handle_request(self, request: dict) -> dict | None:
        """Route a JSON-RPC request to the appropriate handler.

        Args:
            request: JSON-RPC request dict

        Returns:
            JSON-RPC response dict, or None for notifications
        """
        if not isinstance(request, dict):
            return self._error_response(None, -32700, "Parse error")

        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        jsonrpc_version = request.get("jsonrpc", "2.0")

        if jsonrpc_version != "2.0":
            return self._error_response(request_id, -32700, "Parse error")

        if not isinstance(method, str):
            return self._error_response(request_id, -32700, "Parse error")

        if method == "initialize":
            result = await self._handle_initialize(params)
            return self._success_response(request_id, result)
        elif method == "shutdown":
            self._should_shutdown = True
            return self._success_response(request_id, None)
        else:
            if self._dispatcher is not None:
                return await self._dispatcher.dispatch(request)
            return self._error_response(request_id, -32601, "Method not found")

    async def _handle_initialize(self, params: Any) -> dict:
        """Handle the initialize method.

        Returns initialization response with server capabilities.
        """
        return {
            "capabilities": {
                "streaming": True,
                "tools": True,
                "sessions": True,
            },
            "version": "0.1.0",
        }

    def _success_response(self, request_id: Any, result: Any) -> dict:
        """Format a JSON-RPC success response."""
        if request_id is None:
            return {}

        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id,
        }

    def _error_response(self, request_id: Any, code: int, message: str) -> dict | None:
        """Format a JSON-RPC error response."""
        if request_id is None:
            return None

        return {
            "jsonrpc": "2.0",
            "error": {
                "code": code,
                "message": message,
            },
            "id": request_id,
        }

    async def send_response(self, request_id: int | str, result: Any) -> None:
        """Send a successful response to a request.

        Args:
            request_id: The ID from the original request
            result: The result to send back
        """
        response = self._success_response(request_id, result)
        if response:
            await self._write_response(response)

    async def send_error(self, request_id: int | str | None, code: int, message: str) -> None:
        """Send an error response.

        Args:
            request_id: The ID from the original request (or None)
            code: JSON-RPC error code
            message: Error message
        """
        response = self._error_response(request_id, code, message)
        if response:
            await self._write_response(response)

    async def send_notification(self, method: str, params: dict) -> None:
        """Send a notification (no ID, no response expected).

        Args:
            method: Method name
            params: Method parameters
        """
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        await self._write_response(notification)

    async def shutdown(self) -> None:
        """Clean up and shutdown the server."""
        logger.debug("Server shutdown complete")

"""JSON-RPC permission handler for TUI interaction."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import uuid4

from sage.permissions.base import PermissionAction, PermissionDecision, PermissionProtocol

logger = logging.getLogger(__name__)

DEFAULT_PERMISSION_TIMEOUT = 60.0


class JsonRpcPermissionHandler(PermissionProtocol):
    """Permission handler that sends permission requests to TUI via JSON-RPC.

    When a tool requires an interactive decision:
    1. Send a ``permission/request`` notification to the TUI.
    2. Create an ``asyncio.Future`` and wait for ``permission/respond``.
    3. Map TUI decision to :class:`PermissionDecision`.

    Supports session-scoped approval: ``allow_session`` caches approval for
    tool+pattern combinations so subsequent identical calls auto-approve.
    """

    def __init__(
        self,
        server: Any,
        dispatcher: Any,
        timeout: float = DEFAULT_PERMISSION_TIMEOUT,
    ) -> None:
        self._server = server
        self._dispatcher = dispatcher
        self._timeout = timeout
        self._session_approvals: dict[str, set[str]] = {}
        self._current_session_id: str | None = None

    def reset_session(self, session_id: str | None = None) -> None:
        """Reset session-scoped approvals when the session changes."""
        if session_id != self._current_session_id:
            self._session_approvals.clear()
            self._current_session_id = session_id

    async def check(self, tool_name: str, arguments: dict[str, Any]) -> PermissionDecision:
        """Check permission for a tool call.

        If the tool has a session-scoped approval, auto-approve.
        Otherwise, send ``permission/request`` to TUI and await a response.
        """
        cache_key = self._make_cache_key(tool_name, arguments)
        cached_patterns = self._session_approvals.get(tool_name)
        if cached_patterns and (cache_key in cached_patterns or "*" in cached_patterns):
            logger.debug("Auto-approved %s via session scope", tool_name)
            return PermissionDecision(
                action=PermissionAction.ALLOW,
                reason="Session-scoped approval",
            )

        request_id = str(uuid4())
        future = self._dispatcher.create_permission_future(request_id)

        await self._server.send_notification(
            "permission/request",
            {
                "id": request_id,
                "request_id": request_id,
                "requestId": request_id,
                "tool": tool_name,
                "arguments": arguments,
                "riskLevel": self._assess_risk(tool_name, arguments),
            },
        )

        try:
            response = await asyncio.wait_for(future, timeout=self._timeout)
        except asyncio.TimeoutError:
            self._dispatcher.pending_permissions.pop(request_id, None)
            logger.warning("Permission request timed out for %s", tool_name)
            return PermissionDecision(
                action=PermissionAction.DENY,
                reason=f"Permission request timed out after {self._timeout}s",
            )

        return self._process_response(tool_name, arguments, response)

    def _process_response(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        response: dict[str, Any],
    ) -> PermissionDecision:
        """Map TUI response payload to :class:`PermissionDecision`."""
        decision = response.get("decision", "deny")

        if decision == "allow_once":
            return PermissionDecision(action=PermissionAction.ALLOW)

        if decision == "allow_always":
            self._session_approvals.setdefault(tool_name, set()).add("*")
            return PermissionDecision(action=PermissionAction.ALLOW, reason="Always allowed")

        if decision == "allow_session":
            cache_key = self._make_cache_key(tool_name, arguments)
            self._session_approvals.setdefault(tool_name, set()).add(cache_key)
            return PermissionDecision(
                action=PermissionAction.ALLOW, reason="Session-scoped approval"
            )

        if decision == "deny":
            reason = response.get("reason", f"User denied execution of '{tool_name}'")
            return PermissionDecision(action=PermissionAction.DENY, reason=reason)

        if decision == "edit":
            return PermissionDecision(action=PermissionAction.ALLOW, reason="Allowed with edits")

        logger.warning("Unknown permission decision: %s", decision)
        return PermissionDecision(
            action=PermissionAction.DENY, reason=f"Unknown decision: {decision}"
        )

    @staticmethod
    def _make_cache_key(tool_name: str, arguments: dict[str, Any]) -> str:
        """Create a cache key from tool name and relevant argument pattern."""
        if "command" in arguments:
            return f"{tool_name}:{arguments['command']}"
        if "path" in arguments:
            return f"{tool_name}:{arguments['path']}"
        if "file_path" in arguments:
            return f"{tool_name}:{arguments['file_path']}"
        return f"{tool_name}:*"

    @staticmethod
    def _assess_risk(tool_name: str, arguments: dict[str, Any]) -> str:
        """Assess risk level of a tool call for UI presentation."""
        high_risk_tools = {"shell", "file_write", "file_edit", "http_request"}
        medium_risk_tools = {"file_read", "git_commit", "git_branch"}

        if tool_name in high_risk_tools:
            cmd = arguments.get("command", "")
            if isinstance(cmd, str) and any(
                pattern in cmd for pattern in ["rm -rf", "sudo", "chmod 777", "> /dev/"]
            ):
                return "critical"
            return "high"

        if tool_name in medium_risk_tools:
            return "medium"

        return "low"

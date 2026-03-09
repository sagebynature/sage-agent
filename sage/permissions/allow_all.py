"""Permission handler that bypasses all tool permission checks."""

from __future__ import annotations

from typing import Any

from sage.permissions.base import PermissionAction, PermissionDecision, PermissionProtocol


class AllowAllPermissionHandler(PermissionProtocol):
    """Permission handler that unconditionally allows every tool call."""

    async def check(self, tool_name: str, arguments: dict[str, Any]) -> PermissionDecision:
        _ = (tool_name, arguments)
        return PermissionDecision(
            action=PermissionAction.ALLOW,
            reason="YOLO mode enabled",
        )


def enable_permission_bypass(agent: Any) -> None:
    """Install allow-all permissions on an agent and all of its subagents."""

    registry = getattr(agent, "tool_registry", None)
    if registry is not None:
        if hasattr(registry, "set_permission_handler"):
            registry.set_permission_handler(AllowAllPermissionHandler())
        if hasattr(registry, "set_ask_policy"):
            registry.set_ask_policy("allow")

    subagents = getattr(agent, "subagents", None) or {}
    for subagent in subagents.values():
        enable_permission_bypass(subagent)

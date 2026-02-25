"""Interactive permission handler with user-consent callbacks."""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from sage.permissions.base import PermissionAction, PermissionDecision
from sage.permissions.policy import PolicyPermissionHandler, PermissionRule

logger = logging.getLogger(__name__)

# Type alias for the ask callback.
AskCallback = Callable[[str, dict[str, Any]], Awaitable[bool]]


class InteractivePermissionHandler:
    """Permission handler that prompts users when action is ASK.

    Wraps :class:`PolicyPermissionHandler` for rule evaluation, then
    invokes an async callback for ASK decisions.  The callback receives
    the tool name and arguments and returns True (approved) or False (denied).
    """

    def __init__(
        self,
        rules: list[PermissionRule],
        default: PermissionAction = PermissionAction.ASK,
        ask_callback: AskCallback | None = None,
    ) -> None:
        self._policy = PolicyPermissionHandler(rules=rules, default=default)
        self._ask_callback = ask_callback

    async def check(self, tool_name: str, arguments: dict[str, Any]) -> PermissionDecision:
        decision = await self._policy.check(tool_name, arguments)

        if decision.action != PermissionAction.ASK:
            return decision

        # ASK — invoke callback.
        if self._ask_callback is None:
            # No callback configured — deny by default for safety.
            return PermissionDecision(
                action=PermissionAction.DENY,
                reason="No ask callback configured; denied by default.",
                destructive=decision.destructive,
            )

        approved = await self._ask_callback(tool_name, arguments)
        if approved:
            return PermissionDecision(
                action=PermissionAction.ALLOW,
                destructive=decision.destructive,
            )
        return PermissionDecision(
            action=PermissionAction.DENY,
            reason=f"User denied execution of '{tool_name}'.",
            destructive=decision.destructive,
        )

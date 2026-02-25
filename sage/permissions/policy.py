"""Config-driven permission handler with pattern matching."""

from __future__ import annotations

import fnmatch
import logging
from typing import Any

from pydantic import BaseModel

from sage.permissions.base import PermissionAction, PermissionDecision

logger = logging.getLogger(__name__)


class PermissionRule(BaseModel):
    """A single permission rule for a tool."""

    tool: str
    action: PermissionAction = PermissionAction.ASK
    patterns: dict[str, str] | None = None


class PolicyPermissionHandler:
    """Permission handler that evaluates config-driven rules.

    **Matching semantics: last match wins.**

    Rules are evaluated in order for a matching tool name; the **last**
    matching rule wins.  This allows broad defaults to be defined first
    and specific overrides to follow.

    Example::

        rules:
          - tool: shell
            action: deny           # Default: deny all shell commands
          - tool: shell
            action: allow
            patterns:
              "git *": allow       # Override: allow git commands
              "rm *": deny         # Override: deny rm commands

    Within a matching rule that carries ``patterns``, pattern matching is
    applied to the ``command`` argument using :func:`fnmatch.fnmatch` —
    again, last matching pattern wins.

    Note: This differs from "first match wins" used by some firewall-style
    systems.  The rationale is that specific overrides are typically added
    after general rules, and "last wins" makes this natural to express.
    """

    def __init__(
        self,
        rules: list[PermissionRule],
        default: PermissionAction = PermissionAction.ASK,
    ) -> None:
        self.rules = rules
        self.default = default

    async def check(self, tool_name: str, arguments: dict[str, Any]) -> PermissionDecision:
        # Find all matching rules (last wins).
        matched_rule: PermissionRule | None = None
        for rule in self.rules:
            if rule.tool == tool_name:
                matched_rule = rule

        if matched_rule is None:
            return PermissionDecision(action=self.default)

        # If the rule has patterns, match against the command argument.
        if matched_rule.patterns:
            command = arguments.get("command", "")
            if not command:
                return PermissionDecision(
                    action=matched_rule.action,
                )

            # Evaluate patterns — last match wins.
            resolved_action = matched_rule.action
            for pattern, action_str in matched_rule.patterns.items():
                if fnmatch.fnmatch(command, pattern):
                    resolved_action = PermissionAction(action_str)

            return PermissionDecision(
                action=resolved_action,
            )

        return PermissionDecision(
            action=matched_rule.action,
        )

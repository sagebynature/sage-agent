"""Config-driven permission handler with pattern matching."""

from __future__ import annotations

import fnmatch
from typing import Any

from pydantic import AliasChoices, BaseModel, Field, model_validator

from sage.permissions.base import PermissionAction, PermissionDecision
from sage.tools.registry import CATEGORY_ARG_MAP, CATEGORY_TOOLS


def _build_tool_category_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for category, tools in CATEGORY_TOOLS.items():
        for tool in tools:
            mapping[tool] = category
    return mapping


TOOL_TO_CATEGORY = _build_tool_category_map()


class CategoryPermissionRule(BaseModel):
    """A single permission rule for a tool category."""

    category: str = Field(validation_alias=AliasChoices("category", "tool"))
    action: PermissionAction = PermissionAction.ASK
    patterns: dict[str, PermissionAction] | None = None

    @model_validator(mode="after")
    def normalize_category(self) -> CategoryPermissionRule:
        if self.category in TOOL_TO_CATEGORY:
            self.category = TOOL_TO_CATEGORY[self.category]
        return self


PermissionRule = CategoryPermissionRule


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
        rules: list[CategoryPermissionRule],
        default: PermissionAction = PermissionAction.ASK,
    ) -> None:
        self.rules = rules
        self.default = default

    async def check(self, tool_name: str, arguments: dict[str, Any]) -> PermissionDecision:
        category = TOOL_TO_CATEGORY.get(tool_name)
        if category is None:
            return PermissionDecision(action=self.default)

        matched_rule: CategoryPermissionRule | None = None
        for rule in self.rules:
            if rule.category == category:
                matched_rule = rule

        if matched_rule is None:
            return PermissionDecision(action=self.default)

        if not matched_rule.patterns:
            return PermissionDecision(action=matched_rule.action)

        arg_value: Any = None
        if category == "edit":
            arg_value = arguments.get("path") or arguments.get("file_path")
        else:
            arg_name = CATEGORY_ARG_MAP.get(category)
            if arg_name is not None:
                arg_value = arguments.get(arg_name)

        if not arg_value:
            return PermissionDecision(action=matched_rule.action)

        resolved_action = matched_rule.action
        for pattern, action in matched_rule.patterns.items():
            if fnmatch.fnmatch(str(arg_value), pattern):
                resolved_action = PermissionAction(action)

        return PermissionDecision(action=resolved_action)

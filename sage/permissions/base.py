"""Permission protocol and base types."""

from __future__ import annotations

from enum import Enum
from typing import Any, runtime_checkable

from pydantic import BaseModel

from typing import Protocol


class PermissionAction(str, Enum):
    """Actions a permission handler can take."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class PermissionDecision(BaseModel):
    """Result of a permission check."""

    action: PermissionAction
    reason: str | None = None
    destructive: bool = False


@runtime_checkable
class PermissionProtocol(Protocol):
    """Protocol for permission handlers."""

    async def check(self, tool_name: str, arguments: dict[str, Any]) -> PermissionDecision: ...

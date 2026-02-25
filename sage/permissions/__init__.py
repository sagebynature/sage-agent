"""Permission and safety model for Sage."""

from sage.permissions.base import (
    PermissionAction,
    PermissionDecision,
    PermissionProtocol,
)

__all__ = ["PermissionAction", "PermissionDecision", "PermissionProtocol"]

"""Permission and safety model for Sage."""

from sage.permissions.allow_all import AllowAllPermissionHandler, enable_permission_bypass
from sage.permissions.base import (
    PermissionAction,
    PermissionDecision,
    PermissionProtocol,
)

__all__ = [
    "AllowAllPermissionHandler",
    "PermissionAction",
    "PermissionDecision",
    "PermissionProtocol",
    "enable_permission_bypass",
]

"""Hooks/events system for sage-agent.

Provides:
- ``HookEvent`` — string enum of all lifecycle events.
- ``HookHandler`` — runtime-checkable Protocol for async handlers.
- ``HookRegistry`` — central registry with void (parallel) and modifying
  (sequential) dispatch, priority ordering, and safety guardrails.
"""

from sage.hooks.base import HookEvent, HookHandler
from sage.hooks.registry import HookRegistry

__all__ = ["HookEvent", "HookHandler", "HookRegistry"]

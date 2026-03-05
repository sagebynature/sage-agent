"""Notepad injector hook — injects working memory notes before each LLM call."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from sage.hooks.base import HookEvent
from sage.models import Message


def make_notepad_hook(
    plan_name: str,
    *,
    base_dir: Path | None = None,
) -> Callable[..., Any]:
    """Return a ``PRE_LLM_CALL`` async hook that injects notepad contents.

    The hook reads all sections from the notepad associated with *plan_name*
    and injects their contents as a system-level context block into the
    message list **before** the LLM call is made.

    Args:
        plan_name: The plan name whose notepad should be injected.
        base_dir: Optional base directory for notepad storage.  Primarily
            used in tests to keep data isolated from ``.sage/notepads``.

    Returns:
        An async hook callable compatible with the ``PRE_LLM_CALL`` event.
    """
    from sage.planning.notepad import Notepad

    notepad = Notepad(plan_name, base_dir=base_dir)

    async def _hook(event: HookEvent, data: dict[str, Any]) -> dict[str, Any] | None:
        # Only handle PRE_LLM_CALL events.
        if event is not HookEvent.PRE_LLM_CALL:
            return None

        content = await notepad.read_all()
        if not content:
            return None

        notepad_message = Message(role="system", content=f"[Notepad]\n{content}")

        # Inject the notepad message:
        # - AFTER the first system message if one exists
        # - Prepend if no system message
        messages: list[Message] = data.get("messages", [])
        updated_messages: list[Message] = list(messages)
        first_system_idx: int | None = None
        for idx, msg in enumerate(updated_messages):
            if msg.role == "system":
                first_system_idx = idx
                break

        if first_system_idx is not None:
            updated_messages.insert(first_system_idx + 1, notepad_message)
        else:
            updated_messages.insert(0, notepad_message)

        data["messages"] = updated_messages
        return data

    return _hook

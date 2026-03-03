"""Base types for the hooks/events system."""

from __future__ import annotations

import enum
from typing import Any, Protocol, runtime_checkable


class HookEvent(str, enum.Enum):
    """All hook events that can be emitted in the agent lifecycle."""

    PRE_LLM_CALL = "pre_llm_call"
    POST_LLM_CALL = "post_llm_call"
    PRE_TOOL_EXECUTE = "pre_tool_execute"
    POST_TOOL_EXECUTE = "post_tool_execute"
    PRE_COMPACTION = "pre_compaction"
    POST_COMPACTION = "post_compaction"
    PRE_MEMORY_RECALL = "pre_memory_recall"
    POST_MEMORY_STORE = "post_memory_store"
    ON_DELEGATION = "on_delegation"
    ON_DELEGATION_COMPLETE = "on_delegation_complete"
    ON_LLM_STREAM_DELTA = "on_llm_stream_delta"
    ON_COMPACTION = "on_compaction"
    BACKGROUND_TASK_COMPLETED = "background_task_completed"
    ON_PLAN_CREATED = "on_plan_created"


@runtime_checkable
class HookHandler(Protocol):
    """Protocol for hook handlers.

    A handler is an async callable that receives an event and a data dict.

    - Void handlers return ``None`` (side-effect only).
    - Modifying handlers return a ``dict`` with the (possibly mutated) data.
    """

    async def __call__(self, event: HookEvent, data: dict[str, Any]) -> dict[str, Any] | None: ...

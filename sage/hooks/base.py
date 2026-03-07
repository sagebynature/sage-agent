"""Base types for the hooks/events system."""

from __future__ import annotations

import enum
from typing import Any, Protocol, runtime_checkable


class HookEvent(str, enum.Enum):
    """All hook events that can be emitted in the agent lifecycle."""

    ON_RUN_STARTED = "on_run_started"
    ON_RUN_COMPLETED = "on_run_completed"
    ON_RUN_FAILED = "on_run_failed"
    ON_RUN_CANCELLED = "on_run_cancelled"
    PRE_LLM_CALL = "pre_llm_call"
    POST_LLM_CALL = "post_llm_call"
    ON_LLM_ERROR = "on_llm_error"
    ON_LLM_RETRY = "on_llm_retry"
    PRE_TOOL_EXECUTE = "pre_tool_execute"
    POST_TOOL_EXECUTE = "post_tool_execute"
    ON_TOOL_FAILED = "on_tool_failed"
    ON_TOOL_SKIPPED = "on_tool_skipped"
    PRE_PERMISSION_CHECK = "pre_permission_check"
    POST_PERMISSION_CHECK = "post_permission_check"
    PRE_COMPACTION = "pre_compaction"
    POST_COMPACTION = "post_compaction"
    PRE_MEMORY_RECALL = "pre_memory_recall"
    POST_MEMORY_RECALL = "post_memory_recall"
    PRE_MEMORY_STORE = "pre_memory_store"
    POST_MEMORY_STORE = "post_memory_store"
    ON_MEMORY_ERROR = "on_memory_error"
    ON_DELEGATION = "on_delegation"
    ON_DELEGATION_COMPLETE = "on_delegation_complete"
    ON_DELEGATION_FAILED = "on_delegation_failed"
    ON_LLM_STREAM_DELTA = "on_llm_stream_delta"
    ON_COMPACTION = "on_compaction"
    ON_COMPACTION_FAILED = "on_compaction_failed"
    ON_BACKGROUND_TASK_STARTED = "on_background_task_started"
    BACKGROUND_TASK_COMPLETED = "background_task_completed"
    ON_BACKGROUND_TASK_FAILED = "on_background_task_failed"
    ON_BACKGROUND_TASK_CANCELLED = "on_background_task_cancelled"
    ON_SESSION_STARTED = "on_session_started"
    ON_SESSION_RESUMED = "on_session_resumed"
    ON_SESSION_CLOSED = "on_session_closed"
    ON_MESSAGE_SENT = "on_message_sent"
    ON_MESSAGE_RECEIVED = "on_message_received"
    ON_MESSAGE_EXPIRED = "on_message_expired"
    ON_DEAD_LETTER = "on_dead_letter"
    ON_PLAN_CREATED = "on_plan_created"


@runtime_checkable
class HookHandler(Protocol):
    """Protocol for hook handlers.

    A handler is an async callable that receives an event and a data dict.

    - Void handlers return ``None`` (side-effect only).
    - Modifying handlers return a ``dict`` with the (possibly mutated) data.
    """

    async def __call__(self, event: HookEvent, data: dict[str, Any]) -> dict[str, Any] | None: ...

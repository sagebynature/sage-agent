from __future__ import annotations

from typing import TYPE_CHECKING

from sage.exceptions import ToolError
from sage.models import ToolSchema

if TYPE_CHECKING:
    from sage.agent import Agent


def register_background_tools(agent: "Agent") -> None:
    subagent_names = list(agent.subagents.keys())
    agent_ref = agent

    async def delegate_background(agent_name: str, task: str, session_id: str | None = None) -> str:  # noqa: D401
        sub = agent_ref.subagents.get(agent_name)
        if sub is None:
            available = ", ".join(sorted(agent_ref.subagents))
            raise ToolError(f"Unknown subagent: {agent_name}. Available: {available}")
        task_id = await agent_ref._bg_manager.launch(
            sub, task, session_id=session_id, parent_agent=agent_ref
        )
        return f"Background task launched: {task_id} (agent={agent_name})"

    delegate_bg_schema = ToolSchema(
        name="delegate_background",
        description="Launch a subagent task in the background. Returns immediately with a task_id.",
        parameters={
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": f"Name of the subagent. One of: {subagent_names}",
                    "enum": subagent_names,
                },
                "task": {
                    "type": "string",
                    "description": "The task or input to send to the subagent.",
                },
                "session_id": {
                    "type": "string",
                    "description": "Optional session ID to resume a previous background conversation.",
                },
            },
            "required": ["agent_name", "task"],
        },
    )
    delegate_background.__tool_schema__ = delegate_bg_schema  # type: ignore[attr-defined]
    agent.tool_registry.register(delegate_background)

    async def collect_result(task_id: str) -> str:  # noqa: D401
        info = agent_ref._bg_manager.get(task_id)
        if info is None:
            return f"Unknown task_id: {task_id}"
        if info.status == "running":
            return f"Task {task_id} is still running (agent={info.agent_name})."
        agent_ref._bg_manager.mark_notified(task_id)
        if info.status == "completed":
            return info.result or "(empty result)"
        if info.status == "failed":
            return f"Task failed: {info.error or 'unknown error'}"
        return f"Task status: {info.status}"

    collect_schema = ToolSchema(
        name="collect_result",
        description="Collect the result of a background task by task_id.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The task_id returned by delegate_background.",
                },
            },
            "required": ["task_id"],
        },
    )
    collect_result.__tool_schema__ = collect_schema  # type: ignore[attr-defined]
    agent.tool_registry.register(collect_result)

    async def cancel_background_task(task_id: str) -> str:  # noqa: D401
        cancelled = agent_ref._bg_manager.cancel(task_id)
        if cancelled:
            return f"Task {task_id} cancelled."
        return f"Task {task_id} not found or already finished."

    cancel_schema = ToolSchema(
        name="cancel_background_task",
        description="Cancel a running background task.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The task_id to cancel.",
                },
            },
            "required": ["task_id"],
        },
    )
    cancel_background_task.__tool_schema__ = cancel_schema  # type: ignore[attr-defined]
    agent.tool_registry.register(cancel_background_task)

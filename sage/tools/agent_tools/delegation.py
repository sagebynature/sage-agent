from __future__ import annotations

from typing import TYPE_CHECKING

from sage.models import ToolSchema

if TYPE_CHECKING:
    from sage.agent import Agent


def register_delegation_tools(agent: "Agent") -> None:
    subagent_names = list(agent.subagents.keys())
    description_lines = [
        "Delegate a task to a subagent and return its response.",
        "",
        "Available subagents:",
    ]
    for name in subagent_names:
        sub = agent.subagents[name]
        desc = sub.description or "(no description)"
        description_lines.append(f"  - {name}: {desc}")

    agent_ref = agent

    async def delegate(  # noqa: D401
        agent_name: str,
        task: str,
        session_id: str | None = None,
        category: str | None = None,
    ) -> str:
        return await agent_ref.delegate(
            agent_name,
            task,
            session_id=session_id,
            category=category,
        )

    schema = ToolSchema(
        name="delegate",
        description="\n".join(description_lines),
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
                    "description": "Optional session ID to resume a previous conversation with this subagent.",
                },
                "category": {
                    "type": "string",
                    "description": "Task category for model routing (e.g., 'quick', 'deep').",
                },
            },
            "required": ["agent_name", "task"],
        },
    )
    delegate.__tool_schema__ = schema  # type: ignore[attr-defined]
    agent.tool_registry.register(delegate)

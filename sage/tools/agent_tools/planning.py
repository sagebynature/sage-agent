from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sage.hooks.base import HookEvent
from sage.models import ToolMetadata, ToolSchema
from sage.planning.notepad import Notepad
from sage.planning.state import PlanState, PlanStateManager, PlanTask

if TYPE_CHECKING:
    from sage.agent import Agent


def register_planning_tools(agent: Agent, config: Any) -> None:
    manager = PlanStateManager()
    agent_ref = agent

    async def plan_create(name: str, description: str, tasks: list[str]) -> str:
        plan = PlanState(
            plan_name=name,
            description=description,
            tasks=[PlanTask(description=t) for t in tasks],
        )
        manager.save(plan)

        if agent_ref._hook_registry:
            data = {"plan": plan, "agent": agent_ref, "analysis": None}
            data = await agent_ref._hook_registry.emit_modifying(HookEvent.ON_PLAN_CREATED, data)
            analysis = data.get("analysis")
            if analysis:
                return (
                    f"Plan '{name}' created with {len(tasks)} tasks.\n\n**Analysis:**\n{analysis}"
                )

        return f"Plan '{name}' created with {len(tasks)} tasks."

    create_schema = ToolSchema(
        name="plan_create",
        description="Create a new structured plan with named tasks.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Unique plan name."},
                "description": {
                    "type": "string",
                    "description": "What this plan accomplishes.",
                },
                "tasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered list of task descriptions.",
                },
            },
            "required": ["name", "description", "tasks"],
        },
        metadata=ToolMetadata(
            risk_level="low",
            stateful=True,
            resource_kind="none",
            approval_hint="Creates or revises an internal work plan.",
            idempotent=False,
        ),
    )
    plan_create.__tool_schema__ = create_schema  # type: ignore[attr-defined]
    agent.tool_registry.register(plan_create)

    async def plan_status(plan_name: str | None = None) -> str:
        if plan_name:
            plan = manager.load(plan_name)
            if not plan:
                return f"Plan '{plan_name}' not found."
            lines = [f"Plan: {plan.plan_name}", f"Description: {plan.description}", "Tasks:"]
            for i, t in enumerate(plan.tasks):
                lines.append(f"  {i + 1}. [{t.status}] {t.description}")
                if t.result:
                    lines.append(f"     Result: {t.result}")
            return "\n".join(lines)
        names = manager.list_active()
        if not names:
            return "No active plans."
        return "Active plans:\n" + "\n".join(f"  - {n}" for n in names)

    status_schema = ToolSchema(
        name="plan_status",
        description="Show status of a specific plan or list all active plans.",
        parameters={
            "type": "object",
            "properties": {
                "plan_name": {
                    "type": "string",
                    "description": "Plan name to inspect. Omit to list all plans.",
                },
            },
            "required": [],
        },
        metadata=ToolMetadata(
            risk_level="low",
            stateful=True,
            resource_kind="none",
            approval_hint="Reads internal plan state.",
            idempotent=True,
        ),
    )
    plan_status.__tool_schema__ = status_schema  # type: ignore[attr-defined]
    agent.tool_registry.register(plan_status)

    async def plan_update(
        plan_name: str, task_index: int, status: str, result: str | None = None
    ) -> str:
        plan = manager.load(plan_name)
        if not plan:
            return f"Plan '{plan_name}' not found."
        if task_index < 0 or task_index >= len(plan.tasks):
            return f"Invalid task index {task_index}. Plan has {len(plan.tasks)} tasks."
        task = plan.tasks[task_index]
        task.status = status  # type: ignore[assignment]
        if result is not None:
            task.result = result
        manager.save(plan)
        return f"Task {task_index} updated to '{status}'."

    update_schema = ToolSchema(
        name="plan_update",
        description="Update the status of a task within a plan.",
        parameters={
            "type": "object",
            "properties": {
                "plan_name": {"type": "string", "description": "Name of the plan."},
                "task_index": {
                    "type": "integer",
                    "description": "Zero-based index of the task to update.",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "failed"],
                    "description": "New status for the task.",
                },
                "result": {
                    "type": "string",
                    "description": "Optional result or note for the task.",
                },
            },
            "required": ["plan_name", "task_index", "status"],
        },
        metadata=ToolMetadata(
            risk_level="low",
            stateful=True,
            resource_kind="none",
            approval_hint="Updates internal plan progress.",
            idempotent=False,
        ),
    )
    plan_update.__tool_schema__ = update_schema  # type: ignore[attr-defined]
    agent.tool_registry.register(plan_update)

    if config.planning and config.planning.review and config.planning.review.enabled:
        from sage.planning.review import LLMPlanReviewer, review_loop

        async def plan_review(plan_name: str) -> str:
            plan = manager.load(plan_name)
            if not plan:
                return f"Plan '{plan_name}' not found."

            reviewer = LLMPlanReviewer(agent_ref, prompt=config.planning.review.prompt)

            async def _reviser(p: PlanState, feedback: list[str]) -> PlanState:
                from sage.models import Message

                revision_prompt = (
                    f"Revise this plan based on feedback.\n\n"
                    f"Plan: {p.plan_name}\nTasks:\n"
                    + "\n".join(f"  {i + 1}. {t.description}" for i, t in enumerate(p.tasks))
                    + "\n\nFeedback:\n"
                    + "\n".join(f"- {f}" for f in feedback)
                    + "\n\nReturn the revised task list, one per line, prefixed with '- '."
                )
                resp = await agent_ref.provider.complete(
                    messages=[Message(role="user", content=revision_prompt)]
                )
                new_tasks = [
                    PlanTask(description=line.strip().lstrip("- "))
                    for line in (resp.message.content or "").splitlines()
                    if line.strip().startswith("- ")
                ]
                if new_tasks:
                    p.tasks = new_tasks
                manager.save(p)
                return p

            max_iter = config.planning.review.max_iterations
            final_plan, result = await review_loop(
                plan, reviewer, _reviser, max_iterations=max_iter
            )
            manager.save(final_plan)

            status_str = "Approved" if result.approved else "Not approved (max iterations reached)"
            feedback_str = (
                "\n".join(f"  - {f}" for f in result.feedback) if result.feedback else "  None"
            )
            return f"Review: {status_str}\nFeedback:\n{feedback_str}"

        review_schema = ToolSchema(
            name="plan_review",
            description="Run an iterative review loop on a plan to check for issues.",
            parameters={
                "type": "object",
                "properties": {
                    "plan_name": {
                        "type": "string",
                        "description": "Name of the plan to review.",
                    },
                },
                "required": ["plan_name"],
            },
            metadata=ToolMetadata(
                risk_level="low",
                stateful=True,
                resource_kind="none",
                approval_hint="Reviews and potentially revises an internal plan.",
                idempotent=False,
            ),
        )
        plan_review.__tool_schema__ = review_schema  # type: ignore[attr-defined]
        agent.tool_registry.register(plan_review)

    notepad_instance = Notepad("default")

    async def notepad_write(section: str, content: str, append: bool = True) -> str:
        await notepad_instance.write(section, content, append=append)
        return f"Written to notepad section '{section}'."

    write_schema = ToolSchema(
        name="notepad_write",
        description="Write content to a named section of the working notepad.",
        parameters={
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": "Section name (e.g. 'learnings', 'decisions', 'todo').",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write.",
                },
                "append": {
                    "type": "boolean",
                    "description": "Append to existing content (true) or overwrite (false). Defaults to true.",
                },
            },
            "required": ["section", "content"],
        },
        metadata=ToolMetadata(
            risk_level="low",
            stateful=True,
            resource_kind="none",
            approval_hint="Writes to the agent's planning notepad.",
            idempotent=False,
        ),
    )
    notepad_write.__tool_schema__ = write_schema  # type: ignore[attr-defined]
    agent.tool_registry.register(notepad_write)

    async def notepad_read(section: str | None = None) -> str:
        if section:
            result = await notepad_instance.read(section)
            return result if result else f"Section '{section}' is empty."
        result = await notepad_instance.read_all()
        return result if result else "Notepad is empty."

    read_schema = ToolSchema(
        name="notepad_read",
        description="Read content from the working notepad.  Omit section to read all sections.",
        parameters={
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": "Section name to read.  Omit to read all sections.",
                },
            },
            "required": [],
        },
        metadata=ToolMetadata(
            risk_level="low",
            stateful=True,
            resource_kind="none",
            approval_hint="Reads the agent's planning notepad.",
            idempotent=True,
        ),
    )
    notepad_read.__tool_schema__ = read_schema  # type: ignore[attr-defined]
    agent.tool_registry.register(notepad_read)

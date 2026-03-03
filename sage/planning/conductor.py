from __future__ import annotations

from typing import Any


class ConductorMixin:
    """Mixin that adds plan-execution orchestration to an agent.

    Iterates through a named plan's tasks in order, skipping already-completed
    or failed tasks, delegating each pending task to the ``executor`` subagent,
    and persisting state after each step.
    """

    async def run_plan(self, plan_name: str, agent: Any) -> str:
        from sage.planning.state import PlanStateManager

        manager = PlanStateManager()
        plan = manager.load(plan_name)
        if not plan:
            return f"Plan {plan_name} not found."

        for task in plan.tasks:
            if task.status in ("completed", "failed"):
                continue

            task.status = "in_progress"
            manager.save(plan)

            result = await agent.delegate("executor", task.description)

            task.result = result
            task.status = "completed"
            manager.save(plan)

        return "Plan execution finished."

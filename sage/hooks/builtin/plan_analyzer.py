"""Optional pre-execution plan analysis hook.

Performs an LLM call to identify gaps, ambiguities, and hidden requirements
in a newly created plan.  Enable via frontmatter::

    planning:
      analysis:
        enabled: true
        prompt: "custom analysis prompt here (optional)"
"""

from __future__ import annotations

import logging
from typing import Any

from sage.hooks.base import HookEvent
from sage.models import Message

logger = logging.getLogger(__name__)

DEFAULT_ANALYSIS_PROMPT = """Analyze the following plan for potential issues:

Plan: {plan_name}
Description: {description}

Tasks:
{tasks}

Identify:
1. Ambiguities — tasks that are underspecified
2. Missing dependencies — tasks that implicitly require something not listed
3. Ordering issues — tasks that should come before/after others
4. Risks — anything that could cause the plan to fail

Be concise. If the plan looks solid, say so briefly."""


def make_plan_analyzer(prompt: str | None = None) -> Any:
    """Factory returning an ON_PLAN_CREATED hook that analyzes new plans.

    Args:
        prompt: Custom analysis prompt template.  Must contain ``{plan_name}``,
                ``{description}``, and ``{tasks}`` placeholders.  Falls back to
                ``DEFAULT_ANALYSIS_PROMPT`` if not provided.

    Returns:
        An async modifying hook function.
    """
    analysis_prompt = prompt or DEFAULT_ANALYSIS_PROMPT

    async def _hook(event: HookEvent, data: dict[str, Any]) -> dict[str, Any]:
        if event != HookEvent.ON_PLAN_CREATED:
            return data

        plan = data["plan"]
        agent = data["agent"]

        task_list = "\n".join(f"  {i + 1}. {t.description}" for i, t in enumerate(plan.tasks))
        filled_prompt = analysis_prompt.format(
            plan_name=plan.plan_name,
            description=plan.description,
            tasks=task_list,
        )

        msg = Message(role="user", content=filled_prompt)
        response = await agent.provider.complete(messages=[msg])
        data["analysis"] = response.content
        return data

    return _hook

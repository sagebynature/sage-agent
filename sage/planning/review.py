"""Plan review protocol, iterative review loop, and default LLM reviewer.

The ``PlanReviewer`` protocol defines the review interface.  Any async
callable ``(PlanState) -> ReviewResult`` satisfies it.  The ``review_loop``
function pairs a reviewer with a reviser for iterative refinement.
``LLMPlanReviewer`` is the shipped reference implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from sage.planning.state import PlanState

logger = logging.getLogger(__name__)


class ReviewResult(BaseModel):
    """Result of a single plan review iteration."""

    approved: bool
    feedback: list[str] = []
    metadata: dict[str, Any] = {}  # Reviewer-defined (scores, tags, etc.)


@runtime_checkable
class PlanReviewer(Protocol):
    """Protocol for plan reviewers.

    Implement this to define custom review logic.  The only requirement
    is an async ``__call__`` that receives a ``PlanState`` and returns a
    ``ReviewResult``.
    """

    async def __call__(self, plan: PlanState) -> ReviewResult: ...


# ---------------------------------------------------------------------------
# Iterative review loop
# ---------------------------------------------------------------------------

DEFAULT_REVIEW_PROMPT = """Review the following plan and evaluate whether it is ready for execution.

Plan: {plan_name}
Description: {description}

Tasks:
{tasks}

Evaluate:
- Is every task specific enough to execute without guesswork?
- Are there verification steps or success criteria?
- Are dependencies between tasks accounted for?

Respond in this exact format:
APPROVED: yes/no
FEEDBACK:
- (one line per issue, or "none" if approved)
"""


async def review_loop(
    plan: PlanState,
    reviewer: PlanReviewer,
    reviser: Any,  # async callable: (PlanState, list[str]) -> PlanState
    *,
    max_iterations: int = 3,
) -> tuple[PlanState, ReviewResult]:
    """Run an iterative review-revise loop on a plan.

    The loop calls *reviewer* to evaluate the plan.  If not approved and
    iterations remain, it calls *reviser* with the feedback to produce a
    revised plan, then reviews again.

    Args:
        plan: The initial plan to review.
        reviewer: Any callable satisfying the ``PlanReviewer`` protocol.
        reviser: An async callable ``(plan, feedback) -> revised_plan``.
        max_iterations: Maximum review-revise cycles.

    Returns:
        A tuple of ``(final_plan, last_review_result)``.
    """
    result: ReviewResult | None = None
    for i in range(max_iterations):
        logger.info("Plan review iteration %d/%d", i + 1, max_iterations)
        result = await reviewer(plan)

        if result.approved:
            logger.info("Plan approved on iteration %d", i + 1)
            return plan, result

        if i < max_iterations - 1:
            logger.info("Plan rejected with %d feedback items, revising", len(result.feedback))
            plan = await reviser(plan, result.feedback)

    assert result is not None  # guaranteed by loop executing at least once
    logger.warning("Plan not approved after %d iterations, proceeding anyway", max_iterations)
    return plan, result


# ---------------------------------------------------------------------------
# Default LLM-based reviewer
# ---------------------------------------------------------------------------


class LLMPlanReviewer:
    """Default plan reviewer that uses an LLM call.

    Args:
        agent: The agent whose provider will be used for the LLM call.
        prompt: Custom review prompt template.  Must contain ``{plan_name}``,
                ``{description}``, and ``{tasks}``.  Falls back to
                ``DEFAULT_REVIEW_PROMPT``.
    """

    def __init__(self, agent: Any, prompt: str | None = None) -> None:
        self._agent = agent
        self._prompt = prompt or DEFAULT_REVIEW_PROMPT

    async def __call__(self, plan: PlanState) -> ReviewResult:
        from sage.models import Message

        task_list = "\n".join(f"  {i + 1}. {t.description}" for i, t in enumerate(plan.tasks))
        filled = self._prompt.format(
            plan_name=plan.plan_name,
            description=plan.description,
            tasks=task_list,
        )

        response = await self._agent.provider.complete(
            messages=[Message(role="user", content=filled)]
        )
        return self._parse_response(response.content)

    @staticmethod
    def _parse_response(text: str) -> ReviewResult:
        """Parse structured LLM response into ``ReviewResult``."""
        lines = text.strip().splitlines()
        approved = False
        feedback: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.lower().startswith("approved:"):
                value = stripped.split(":", 1)[1].strip().lower()
                approved = value in ("yes", "true")
            elif stripped.startswith("- ") and stripped != "- none":
                feedback.append(stripped[2:])

        return ReviewResult(approved=approved, feedback=feedback)

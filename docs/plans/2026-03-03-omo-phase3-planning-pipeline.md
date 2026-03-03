# Phase 3: Planning Pipeline

**Goal:** Give agents the ability to create, persist, analyze, review, and execute multi-step plans — using the same primitives-over-opinions philosophy as the rest of sage-agent.

**Architecture:**
- **Plan Persistence:** A `PlanStateManager` stores structured plans as JSON in `.sage/plans/`. New tools (`plan_create`, `plan_status`, `plan_update`) let any agent manage plans.
- **Pre-Execution Analysis:** A hook-based system (`ON_PLAN_CREATED`) lets users attach their own analysis logic before a plan executes. A default analysis hook ships as an optional built-in.
- **Plan Review:** A `PlanReviewer` protocol defines the review interface. An iterative review loop accepts any implementation. A default reviewer ships as a built-in reference.
- **TUI Integration:** The plan widget shows live progress in the Textual TUI.

**Design Principle:** Provide the mechanism (persistence, hook points, review protocol, iteration loop) — not the policy (specific prompts, fixed rubrics, hardcoded categories). Users compose their own planning workflows on top of these primitives.

**Tech Stack:** Python 3.10+, Pydantic v2, LiteLLM, Pytest, Asyncio

---

### Task 1: Cross-Session Plan Persistence (Boulder State)

**Files:**
- Create: `sage/planning/state.py`
- Modify: `sage/config.py` (Add `PlanningConfig` to `AgentConfig`)
- Modify: `sage/agent.py` (Register planning tools and startup check)

**Step 1: Define Plan Models**
Create structured models for tasks and overall plan state in `sage/planning/state.py`.

```python
# sage/planning/state.py
from pydantic import BaseModel, Field
from typing import Literal
import time

class PlanTask(BaseModel):
    description: str
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: str | None = None
    session_id: str | None = None

class PlanState(BaseModel):
    plan_name: str
    description: str
    tasks: list[PlanTask]
    session_ids: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
```

**Step 2: Implement PlanStateManager**
Add logic to persist and retrieve plans from `.sage/plans/`.

```python
# sage/planning/state.py
from pathlib import Path

class PlanStateManager:
    def __init__(self, base_dir: Path | str = ".sage/plans"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, plan: PlanState) -> Path:
        plan.updated_at = time.time()
        path = self.base_dir / f"{plan.plan_name}.json"
        path.write_text(plan.model_dump_json(indent=2))
        return path

    def load(self, name: str) -> PlanState | None:
        path = self.base_dir / f"{name}.json"
        if not path.exists():
            return None
        return PlanState.model_validate_json(path.read_text())

    def list_active(self) -> list[str]:
        return [p.stem for p in self.base_dir.glob("*.json")]
```

**Step 3: Register Planning Tools in Agent**
Update `Agent._register_delegation_tools` (or a new `_register_planning_tools`) in `sage/agent.py` to expose `plan_create`, `plan_status`, and `plan_update`.

```python
# Shorthand for tools to be registered via @tool or direct closure
async def plan_create(name: str, description: str, tasks: list[str]) -> str:
    plan = PlanState(
        plan_name=name,
        description=description,
        tasks=[PlanTask(description=t) for t in tasks]
    )
    manager.save(plan)
    return f"Plan '{name}' created with {len(tasks)} tasks."
```

**Verification:**
- `pytest tests/test_planning_state.py` verifying JSON persistence round-trip.
- CLI Test: Run `sage agent run --input "Create a plan 'test' with task 'hello'"` then verify `.sage/plans/test.json` exists.

---

### Task 2: Pre-Execution Analysis Hook

**Replaces:** The original "Metis Pattern" gap analysis. Instead of a hardcoded analysis prompt wired into `agent.run()`, this provides a hook point that users can attach any analysis logic to.

**Files:**
- Modify: `sage/hooks/base.py` (Add `ON_PLAN_CREATED` event)
- Create: `sage/hooks/builtin/plan_analyzer.py` (Optional default analyzer)
- Modify: `sage/config.py` (Add `PlanAnalysisConfig` to `AgentConfig`)
- Modify: `sage/agent.py` (Emit `ON_PLAN_CREATED` hook after plan creation)

**Step 1: Add Hook Event**
Extend `HookEvent` in `sage/hooks/base.py`:

```python
# sage/hooks/base.py
class HookEvent(str, enum.Enum):
    # ... existing events ...
    ON_PLAN_CREATED = "on_plan_created"
```

The hook data dict contract for `ON_PLAN_CREATED`:
```python
{
    "plan": PlanState,          # The newly created plan
    "agent": Agent,             # The agent that created it
    "analysis": str | None,     # Populated by modifying hooks (starts as None)
}
```

**Step 2: Emit Hook on Plan Creation**
In the `plan_create` tool (registered in `sage/agent.py`), emit the hook after persisting the plan:

```python
# sage/agent.py (inside plan_create tool)
async def plan_create(name: str, description: str, tasks: list[str]) -> str:
    plan = PlanState(
        plan_name=name,
        description=description,
        tasks=[PlanTask(description=t) for t in tasks],
    )
    manager.save(plan)

    # Emit hook — attached handlers can analyze, validate, or enrich the plan
    if agent_ref.hook_registry:
        data = {"plan": plan, "agent": agent_ref, "analysis": None}
        data = await agent_ref.hook_registry.emit_modifying(HookEvent.ON_PLAN_CREATED, data)

        # If a handler produced analysis, append it to the response
        analysis = data.get("analysis")
        if analysis:
            return f"Plan '{name}' created with {len(tasks)} tasks.\n\n**Analysis:**\n{analysis}"

    return f"Plan '{name}' created with {len(tasks)} tasks."
```

**Step 3: Ship Default Analyzer as Optional Built-in Hook**
Following the same factory pattern as `make_credential_scrubber`:

```python
# sage/hooks/builtin/plan_analyzer.py
"""Optional pre-execution plan analysis hook.

Performs an LLM call to identify gaps, ambiguities, and hidden requirements
in a newly created plan. Enable via frontmatter:

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
        prompt: Custom analysis prompt template. Must contain {plan_name},
                {description}, and {tasks} placeholders. Falls back to
                DEFAULT_ANALYSIS_PROMPT if not provided.

    Returns:
        An async modifying hook function.
    """
    analysis_prompt = prompt or DEFAULT_ANALYSIS_PROMPT

    async def _hook(event: HookEvent, data: dict[str, Any]) -> dict[str, Any]:
        if event != HookEvent.ON_PLAN_CREATED:
            return data

        plan = data["plan"]
        agent = data["agent"]

        task_list = "\n".join(f"  {i+1}. {t.description}" for i, t in enumerate(plan.tasks))
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
```

**Step 4: Config Model**
```python
# sage/config.py
class PlanAnalysisConfig(BaseModel):
    """Configuration for the optional plan analysis hook."""
    enabled: bool = False
    prompt: str | None = None  # Custom analysis prompt template
```

**Step 5: Wire Config to Hook Registration**
In `sage/agent.py`, during hook setup (same pattern as credential scrubbing):

```python
# sage/agent.py (in hook registration logic)
if config.planning and config.planning.analysis and config.planning.analysis.enabled:
    from sage.hooks.builtin.plan_analyzer import make_plan_analyzer
    hook = make_plan_analyzer(prompt=config.planning.analysis.prompt)
    self.hook_registry.register(
        HookEvent.ON_PLAN_CREATED, hook, modifying=True
    )
```

**Usage in frontmatter:**
```yaml
planning:
  analysis:
    enabled: true
    # Optional: override the default analysis prompt
    # prompt: "My custom analysis prompt with {plan_name}, {description}, {tasks}"
```

**Verification:**
- `pytest tests/test_plan_analyzer.py`:
  - With analysis enabled: plan creation returns analysis text.
  - With analysis disabled (default): plan creation returns plain confirmation.
  - With custom prompt: analysis uses the user-provided prompt.
- Hook isolation: analysis hook failure does not prevent plan creation.

---

### Task 3: Plan Review Protocol & Iterative Loop

**Replaces:** The original "Momus Pattern" with a fixed rubric. Instead, this provides a `PlanReviewer` protocol that users implement, paired with a reusable iterative review loop. A default LLM-based reviewer ships as a reference implementation.

**Files:**
- Create: `sage/planning/review.py` (Protocol, loop, and default reviewer)
- Modify: `sage/config.py` (Add `PlanReviewConfig`)

**Step 1: Define the Review Protocol**

```python
# sage/planning/review.py
from __future__ import annotations
from typing import Protocol, runtime_checkable, Any
from pydantic import BaseModel

class ReviewResult(BaseModel):
    """Result of a single plan review iteration."""
    approved: bool
    feedback: list[str] = []
    metadata: dict[str, Any] = {}  # Reviewer-defined (scores, tags, etc.)


@runtime_checkable
class PlanReviewer(Protocol):
    """Protocol for plan reviewers.

    Implement this to define custom review logic. The only requirement
    is an async __call__ that receives a PlanState and returns a ReviewResult.
    """
    async def __call__(self, plan: "PlanState") -> ReviewResult: ...
```

**Step 2: Implement the Iterative Review Loop**
This is the reusable mechanism — it works with any `PlanReviewer` implementation:

```python
# sage/planning/review.py
from sage.planning.state import PlanState
import logging

logger = logging.getLogger(__name__)


async def review_loop(
    plan: PlanState,
    reviewer: PlanReviewer,
    reviser: Any,  # async callable: (PlanState, list[str]) -> PlanState
    *,
    max_iterations: int = 3,
) -> tuple[PlanState, ReviewResult]:
    """Run an iterative review-revise loop on a plan.

    The loop calls `reviewer` to evaluate the plan. If not approved and
    iterations remain, it calls `reviser` with the feedback to produce a
    revised plan, then reviews again.

    Args:
        plan: The initial plan to review.
        reviewer: Any callable satisfying the PlanReviewer protocol.
        reviser: An async callable (plan, feedback) -> revised_plan.
        max_iterations: Maximum review-revise cycles.

    Returns:
        A tuple of (final_plan, last_review_result).
    """
    for i in range(max_iterations):
        logger.info("Plan review iteration %d/%d", i + 1, max_iterations)
        result = await reviewer(plan)

        if result.approved:
            logger.info("Plan approved on iteration %d", i + 1)
            return plan, result

        if i < max_iterations - 1:
            logger.info("Plan rejected with %d feedback items, revising", len(result.feedback))
            plan = await reviser(plan, result.feedback)

    logger.warning("Plan not approved after %d iterations, proceeding anyway", max_iterations)
    return plan, result
```

**Step 3: Ship a Default LLM-Based Reviewer**
This is the reference implementation — users can use it directly or write their own:

```python
# sage/planning/review.py

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


class LLMPlanReviewer:
    """Default plan reviewer that uses an LLM call.

    Args:
        agent: The agent whose provider will be used for the LLM call.
        prompt: Custom review prompt template. Must contain {plan_name},
                {description}, and {tasks}. Falls back to DEFAULT_REVIEW_PROMPT.
    """

    def __init__(self, agent: Any, prompt: str | None = None):
        self._agent = agent
        self._prompt = prompt or DEFAULT_REVIEW_PROMPT

    async def __call__(self, plan: PlanState) -> ReviewResult:
        from sage.models import Message

        task_list = "\n".join(f"  {i+1}. {t.description}" for i, t in enumerate(plan.tasks))
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
        """Parse structured LLM response into ReviewResult."""
        lines = text.strip().splitlines()
        approved = False
        feedback = []

        for line in lines:
            stripped = line.strip()
            if stripped.lower().startswith("approved:"):
                value = stripped.split(":", 1)[1].strip().lower()
                approved = value in ("yes", "true")
            elif stripped.startswith("- ") and stripped != "- none":
                feedback.append(stripped[2:])

        return ReviewResult(approved=approved, feedback=feedback)
```

**Step 4: Config Model**
```python
# sage/config.py
class PlanReviewConfig(BaseModel):
    """Configuration for the optional plan review system."""
    enabled: bool = False
    max_iterations: int = 3
    prompt: str | None = None  # Custom review prompt template
```

**Step 5: Wire as a Planning Tool**
Expose review as an optional tool rather than an automatic gate:

```python
# sage/agent.py (in planning tool registration)
if config.planning and config.planning.review and config.planning.review.enabled:
    async def plan_review(plan_name: str) -> str:
        plan = manager.load(plan_name)
        if not plan:
            return f"Plan '{plan_name}' not found."

        reviewer = LLMPlanReviewer(agent_ref, prompt=config.planning.review.prompt)

        async def reviser(p: PlanState, feedback: list[str]) -> PlanState:
            # Use LLM to revise plan based on feedback
            from sage.models import Message
            revision_prompt = (
                f"Revise this plan based on feedback.\n\n"
                f"Plan: {p.plan_name}\nTasks:\n"
                + "\n".join(f"  {i+1}. {t.description}" for i, t in enumerate(p.tasks))
                + f"\n\nFeedback:\n" + "\n".join(f"- {f}" for f in feedback)
                + "\n\nReturn the revised task list, one per line, prefixed with '- '."
            )
            resp = await agent_ref.provider.complete(
                messages=[Message(role="user", content=revision_prompt)]
            )
            # Parse revised tasks
            new_tasks = [
                PlanTask(description=line.strip().lstrip("- "))
                for line in resp.content.splitlines()
                if line.strip().startswith("- ")
            ]
            if new_tasks:
                p.tasks = new_tasks
            manager.save(p)
            return p

        final_plan, result = await review_loop(
            plan, reviewer, reviser,
            max_iterations=config.planning.review.max_iterations,
        )
        manager.save(final_plan)

        status = "✓ Approved" if result.approved else "✗ Not approved (max iterations reached)"
        feedback_str = "\n".join(f"  - {f}" for f in result.feedback) if result.feedback else "  None"
        return f"Review: {status}\nFeedback:\n{feedback_str}"

    # Register with ToolSchema
```

**Usage in frontmatter:**
```yaml
planning:
  review:
    enabled: true
    max_iterations: 3
    # prompt: "Custom review prompt with {plan_name}, {description}, {tasks}"
```

**Programmatic usage with custom reviewer:**
```python
from sage.planning.review import review_loop, ReviewResult, PlanReviewer

class MyDomainReviewer:
    """Custom reviewer that checks domain-specific constraints."""
    async def __call__(self, plan):
        issues = []
        for task in plan.tasks:
            if "deploy" in task.description and not any("test" in t.description for t in plan.tasks):
                issues.append("Deploy task found but no test task")
        return ReviewResult(approved=len(issues) == 0, feedback=issues)

# Use with the same review_loop
final, result = await review_loop(plan, MyDomainReviewer(), my_reviser)
```

**Verification:**
- `pytest tests/test_plan_review.py`:
  - `review_loop` with an always-approve reviewer returns immediately.
  - `review_loop` with a reject-then-approve reviewer runs exactly 2 iterations.
  - `review_loop` with an always-reject reviewer runs `max_iterations` times.
  - `LLMPlanReviewer._parse_response` correctly parses approved/rejected responses.
- Protocol compliance: Any class with `async __call__(plan) -> ReviewResult` works with `review_loop`.

---

### Task 4: TUI Integration (Plan View)

**Files:**
- Modify: `sage/cli/tui.py`

**Step 1: Add Plan Progress Widget**
Add a sidebar or collapsible widget in the TUI to show the active plan, current task, and overall progress (e.g., "3/5 tasks completed").

**Step 2: Status Updates**
Ensure that when `plan_update` is called by the agent, the TUI refreshes the progress bar/list. Use Textual's reactive attributes or message posting to trigger re-renders.

**Verification:**
- Manual TUI test: Run a multi-step task and watch the plan widget update in real-time.

---

### Summary

| Task | What It Provides | Philosophy |
|------|-----------------|------------|
| 1 — Plan Persistence | `PlanState`, `PlanStateManager`, planning tools | Pure infrastructure primitive |
| 2 — Analysis Hook | `ON_PLAN_CREATED` hook event + optional `make_plan_analyzer` built-in | Mechanism (hook point) + optional policy (default prompt) |
| 3 — Review Protocol | `PlanReviewer` protocol + `review_loop` + optional `LLMPlanReviewer` | Mechanism (protocol + loop) + optional policy (default reviewer) |
| 4 — TUI Plan View | Live progress widget | UX layer on top of primitives |

**What users get out of the box:** Plan persistence, a TUI widget, and optional-but-ready analysis and review that work with zero config beyond `enabled: true`.

**What power users get:** Hook points and protocols they can implement with their own domain logic — a coding agent can check for test coverage in plans, a research agent can verify source diversity, a customer service agent can validate compliance. Same mechanism, any policy.

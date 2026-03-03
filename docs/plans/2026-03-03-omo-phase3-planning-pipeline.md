# Phase 3: Planning Pipeline Implementation Plan

**Goal:** Implement a persistent, verifiable planning pipeline with cross-session continuity, pre-planning gap analysis, and adversarial plan review.

**Architecture:**
- **Persistence (Boulder State):** A JSON-backed state manager (`PlanStateManager`) that tracks plan progress, task statuses, and associated session IDs in a `.sage/plans/` directory.
- **Gap Analysis (Metis):** A pre-planning utility that uses the agent's LLM to classify task intent and identify hidden requirements/ambiguities before a plan is drafted.
- **Plan Review (Momus):** An adversarial review loop that scores generated plans against a rubric (Clarity, Verifiability, Completeness) and iterates until the plan meets quality thresholds.

**Tech Stack:** Python 3.10+, Pydantic v2, Pytest, Asyncio

**Dependencies:**
- Phase 1 (Tool restrictions for secure execution, Session continuity for context)
- Phase 2 (Roles for specialized reviewers, Dynamic prompts for rubric injection)

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
Update `Agent._register_delegation_tools` (or a new `_register_planning_tools`) in `sage/agent.py` to expose `plan_create`, `plan_status`, and `plan_resume`.

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
- `pytest tests/test_planning_state.py` verifying JSON persistence.
- CLI Test: Run `sage agent run --input "Create a plan 'test' with task 'hello'"` then verify `.sage/plans/test.json` exists.

---

### Task 2: Pre-Planning Gap Analysis (Metis Pattern)

**Files:**
- Create: `sage/planning/gap_analysis.py`
- Modify: `sage/config.py` (Add `gap_analysis: bool` to `PlanningConfig`)
- Modify: `sage/agent.py` (Inject analysis into `run()` workflow)

**Step 1: Implement Analysis Utility**
Create a function that performs a specialized LLM call to identify gaps.

```python
# sage/planning/gap_analysis.py
from sage.models import Message

GAP_ANALYSIS_PROMPT = """Analyze the following request for:
1. Intent Classification (Build, Refactor, Research, etc.)
2. Hidden Requirements
3. Ambiguities
4. Constraints (MUST/MUST NOT)

Request: {request}
"""

async def analyze_request(agent: "Agent", request: str) -> str:
    msg = Message(role="user", content=GAP_ANALYSIS_PROMPT.format(request=request))
    # Direct provider call to avoid polluting session history
    response = await agent.provider.complete(messages=[msg])
    return response.content
```

**Step 2: Wire into Agent Execution**
In `sage/agent.py`, if gap analysis is enabled, run it before the main loop and prepend the results to the initial prompt context.

**Verification:**
- Test case: Provide a vague request like "fix the bug".
- Assertion: Gap analysis identifies "Which bug?" and "Where is the logs?" as ambiguities.

---

### Task 3: Plan Review Loop (Momus Pattern)

**Files:**
- Create: `sage/planning/review.py`
- Modify: `sage/config.py` (Add `review: bool` and `max_iterations: int`)

**Step 1: Define Review Rubric and Scoring**
Implement the adversarial review logic in `sage/planning/review.py`.

```python
# sage/planning/review.py
class ReviewResult(BaseModel):
    approved: bool
    feedback: list[str]
    scores: dict[str, int]  # clarity, verifiability, completeness (1-5)

async def review_plan(agent: "Agent", plan: "PlanState") -> ReviewResult:
    # Rubric:
    # - Clarity: Is every step executable?
    # - Verifiability: Is there a 'Verification' section for each task?
    # - Completeness: Does it address all Metis constraints?
    ...
```

**Step 2: Implement Iterative Loop**
In the agent's planning flow, call `review_plan`. If `approved` is False and iterations < `max_iterations`, send feedback back to the planner to revise the plan.

```python
# sage/planning/review.py
async def plan_review_loop(agent, plan, max_iters=3):
    for i in range(max_iters):
        result = await review_plan(agent, plan)
        if result.approved:
            return plan, result
        # Prompt for revision with result.feedback
        plan = await agent.revise_plan(plan, result.feedback)
    return plan, result
```

**Verification:**
- Integration test: A plan missing verification steps is rejected once, then accepted after revision.
- `pytest tests/test_plan_review.py`

---

### Task 4: UI Integration (TUI Plan View)

**Files:**
- Modify: `sage/cli/tui.py`

**Step 1: Add Plan Progress Widget**
Add a sidebar or collapsible widget in the TUI to show the active plan, current task, and overall progress (e.g., "3/5 tasks completed").

**Step 2: Status Updates**
Ensure that when `plan_update` is called by the agent, the TUI refreshes the progress bar/list.

**Verification:**
- Manual TUI test: Run a multi-step task and watch the plan widget update in real-time.

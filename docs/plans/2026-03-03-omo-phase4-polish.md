# Phase 4: Polish Implementation Plan

---

### Task 1: Model-Specific Prompt Overlays

**Files:**
- Create: `sage/prompts/overlays.py`
- Modify: `sage/agent.py`
- Modify: `sage/config.py`

**Step 1: Implement Overlay Registry**
Create `sage/prompts/overlays.py` to define the overlay system.

```python
# sage/prompts/overlays.py
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

@runtime_checkable
class PromptOverlay(Protocol):
    def applies_to(self, model: str) -> bool: ...
    def transform(self, prompt: str) -> str: ...

class GeminiOverlay:
    def applies_to(self, model: str) -> bool:
        return model.startswith("gemini/")

    def transform(self, prompt: str) -> str:
        # Aggressive tool-call enforcement for Gemini
        reminder = "\n\nIMPORTANT: ALWAYS use tools if available. Do not skip tool calls."
        return prompt + reminder

class GPTOverlay:
    def applies_to(self, model: str) -> bool:
        return model.startswith("gpt-")

    def transform(self, prompt: str) -> str:
        # Structured output hints for GPT
        return prompt + "\n\nFormat your reasoning in clear steps."

class OverlayRegistry:
    def __init__(self):
        self._overlays: list[PromptOverlay] = [GeminiOverlay(), GPTOverlay()]

    def apply(self, model: str, prompt: str) -> str:
        for overlay in self._overlays:
            if overlay.applies_to(model):
                prompt = overlay.transform(prompt)
        return prompt

registry = OverlayRegistry()
```

**Step 2: Integrate into Agent**
Refactor `Agent._build_messages` to use a new `_build_system_message` method that applies overlays.

```python
# sage/agent.py

# ... in Agent class ...
def _build_system_message(self) -> str:
    system_parts: list[str] = []
    if self._body:
        system_parts.append(self._body)
    if self._identity_prompt:
        system_parts.append(self._identity_prompt)
    if self.skills:
        # ... skill catalog logic ...
        pass

    base_prompt = "\n\n".join(system_parts)

    # Apply model-specific overlays
    from sage.prompts.overlays import registry as overlay_registry
    return overlay_registry.apply(self.model, base_prompt)

def _build_messages(self, input: str, memory_context: str | None = None) -> list[Message]:
    messages: list[Message] = []

    system_content = self._build_system_message()
    if system_content:
        messages.append(Message(role="system", content=system_content))

    # ... rest of message building ...
```

**Verification:**
- `pytest tests/test_overlays.py` checking that Gemini models receive extra reminders.
- Behavioral check: Run an agent with a `gemini/` model and verify the emitted `PRE_LLM_CALL` hook data contains the overlayed prompt.

---

### Task 2: 3-Layer Planning Architecture (Conductor)

**Files:**
- Create: `sage/planning/conductor.py`
- Create: `examples/orchestrated_agents/planner/AGENTS.md`
- Create: `examples/orchestrated_agents/conductor/AGENTS.md`
- Create: `examples/orchestrated_agents/executor/AGENTS.md`

**Step 1: Implement Conductor logic**
Create `sage/planning/conductor.py` with utilities for task iteration and delegation.

```python
# sage/planning/conductor.py
from sage.planning.state import PlanStateManager, PlanState
from typing import Any

class ConductorMixin:
    async def run_plan(self, plan_name: str, agent: Any):
        manager = PlanStateManager()
        plan = manager.load(plan_name)
        if not plan:
            return f"Plan {plan_name} not found."

        for task in plan.tasks:
            if task.status in ["completed", "failed"]:
                continue

            task.status = "in_progress"
            manager.save(plan)

            # Use agent.delegate to hand off to appropriate subagent
            # Implementation determines subagent based on task description or metadata
            result = await agent.delegate("executor", task.description)

            task.result = result
            task.status = "completed"
            manager.save(plan)

        return "Plan execution finished."
```

**Step 2: Define reference configs**
Create specialized agent configs that use the planning pipeline.

```markdown
---
# examples/orchestrated_agents/conductor/AGENTS.md
name: conductor
model: gpt-4o
subagents:
  - executor
---
You are the Conductor. Read the active plan using `plan_status`.
Iterate through pending tasks and use the `delegate` tool to assign
them to the `executor` subagent.
```

**Verification:**
- CLI Test: `sage agent run examples/orchestrated_agents/conductor/AGENTS.md --input "Execute the plan 'polish-phase'"`
- Verify that the plan state in `.sage/plans/polish-phase.json` transitions from `pending` to `completed`.

---

### Task 3: Notepad / Working Memory System

**Files:**
- Create: `sage/planning/notepad.py`
- Modify: `sage/agent.py` (Register notepad tools)
- Modify: `sage/hooks/builtin/notepad_injector.py` (New hook)

**Step 1: Implement Notepad class**
Create `sage/planning/notepad.py` to manage persistent markdown notes.

```python
# sage/planning/notepad.py
from pathlib import Path

class Notepad:
    def __init__(self, plan_name: str):
        self.base_dir = Path(".sage/notepads") / plan_name
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def write(self, section: str, content: str, append: bool = True):
        path = self.base_dir / f"{section}.md"
        mode = "a" if append else "w"
        with open(path, mode) as f:
            f.write(content + "\n")

    def read_all(self) -> str:
        sections = []
        for path in self.base_dir.glob("*.md"):
            content = path.read_text()
            sections.append(f"### {path.stem.upper()}\n{content}")
        return "\n\n".join(sections)
```

**Step 2: Register Notepad Tools**
Update `Agent.__init__` to register notepad tools when planning is active.

```python
# sage/agent.py

async def notepad_write(section: str, content: str):
    # Logic to find current plan name and write to notepad
    pass

@tool
async def notepad_read() -> str:
    # Logic to read all sections
    pass
```

**Step 3: Implement Context Injection Hook**
Create a hook that injects the notepad content into the system prompt.

```python
# sage/hooks/builtin/notepad_injector.py
from sage.hooks.base import HookEvent

def make_notepad_hook(plan_name: str):
    async def inject_notepad(event, data):
        notepad = Notepad(plan_name)
        content = notepad.read_all()
        if content:
            # Append to system message in data['messages']
            pass
    return inject_notepad
```

**Verification:**
- Run an agent, call `notepad_write("learnings", "The API expects JSON")`.
- Verify `.sage/notepads/{plan}/learnings.md` contains the text.
- Verify in the next turn's `PRE_LLM_CALL` that the notepad content is present in the messages.

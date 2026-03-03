# Phase 2: Async Execution & Specialized Roles Implementation Plan

**Goal:** Enhance `sage-agent` with background task execution, specialized agent roles, and dynamic prompt construction to improve multi-agent orchestration efficiency.

**Architecture:**
- **Background Execution:** A `BackgroundTaskManager` handles non-blocking agent delegations. New tools (`delegate_background`, `collect_result`, `cancel_task`) allow the orchestrator to manage parallel sub-tasks.
- **Specialized Roles:** Role-based profile templates (Consultant, Searcher, Reviewer, Executor) provide pre-configured model defaults and tool restrictions, composing with Phase 1's restriction logic.
- **Dynamic Prompts:** `AgentPromptMetadata` in frontmatter enables automatic construction of delegation tables and selection guides, reducing manual system prompt maintenance.

**Tech Stack:** Python 3.10+, Pydantic v2, Asyncio, LiteLLM

---

### Task 4: Background/Async Agent Execution

**Files:**
- Create: `sage/coordination/background.py` (BackgroundTaskManager and models)
- Modify: `sage/agent.py` (Register background tools, wire TaskManager)
- Modify: `sage/hooks/base.py` (Add `BACKGROUND_TASK_COMPLETED` event)

**Step 1: Create BackgroundTaskManager**
Implement the manager to track and execute agents in the background.

```python
# sage/coordination/background.py
import asyncio
import time
from typing import Literal, Dict, Optional, List
from pydantic import BaseModel, Field

class BackgroundTaskInfo(BaseModel):
    task_id: str
    agent_name: str
    status: Literal["running", "completed", "failed", "cancelled"]
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None
    session_id: Optional[str] = None

class BackgroundTaskManager:
    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}
        self._results: Dict[str, BackgroundTaskInfo] = {}

    async def launch(self, agent: "Agent", task_input: str, session_id: Optional[str] = None) -> str:
        task_id = f"task_{int(time.time() * 1000)}"
        info = BackgroundTaskInfo(task_id=task_id, agent_name=agent.name, status="running", session_id=session_id)
        self._results[task_id] = info

        async def _run():
            try:
                # Assuming stateful delegation logic from Phase 1 is available
                result = await agent.run(task_input)
                info.status = "completed"
                info.result = result
            except asyncio.CancelledError:
                info.status = "cancelled"
                raise
            except Exception as e:
                info.status = "failed"
                info.error = str(e)
            finally:
                info.completed_at = time.time()
                self._tasks.pop(task_id, None)

        self._tasks[task_id] = asyncio.create_task(_run())
        return task_id

    def get_info(self, task_id: str) -> Optional[BackgroundTaskInfo]:
        return self._results.get(task_id)

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task:
            task.cancel()
            return True
        return False
```

**Step 2: Register background tools in Agent**
Modify `_register_delegation_tools` to include background variants.

```python
# sage/agent.py
def _register_delegation_tools(self) -> None:
    # ... existing delegate registration ...

    if not hasattr(self, "_bg_manager"):
        from sage.coordination.background import BackgroundTaskManager
        self._bg_manager = BackgroundTaskManager()

    async def delegate_background(agent_name: str, task: str, session_id: str | None = None) -> str:
        if agent_name not in self.subagents:
            raise ToolError(f"Unknown subagent: {agent_name}")
        subagent = self.subagents[agent_name]
        return await self._bg_manager.launch(subagent, task, session_id=session_id)

    async def collect_result(task_id: str) -> str:
        info = self._bg_manager.get_info(task_id)
        if not info: return "Task not found."
        if info.status == "running": return "Task is still running."
        if info.status == "completed": return info.result
        return f"Task {info.status}: {info.error or ''}"

    # Register with ToolSchema (similar to delegate tool)
```

**Step 3: Implement Completion Notification Hook**
Inject system messages when background tasks finish.

```python
# sage/agent.py (in run loop, before PRE_LLM_CALL)
completed = [t for t in self._bg_manager._results.values() if t.status != "running" and not getattr(t, "_notified", False)]
for t in completed:
    messages.append(Message(role="system", content=f"[BACKGROUND TASK COMPLETED] task_id={t.task_id}, agent={t.agent_name}"))
    t._notified = True
```

**Verification:**
- `pytest tests/test_background.py` (New test file)
- Call `delegate_background`, verify immediate return of `task_id`.
- Wait, call `collect_result`, verify result matches subagent output.

---

### Task 5: Specialized Agent Roles (Pre-configured Profiles)

**Files:**
- Create: `sage/roles/definitions.py` (Role dictionaries)
- Modify: `sage/config.py` (Add `role` to `AgentConfig`)
- Modify: `sage/agent.py` (Resolve role defaults in `from_config`)

**Step 1: Define Role Profiles**
```python
# sage/roles/definitions.py
ROLE_DEFAULTS = {
    "consultant": {
        "model": "gpt-4o",
        "blocked_tools": ["shell", "file_write", "file_edit"],
        "description": "Expert consultant, read-only access."
    },
    "searcher": {
        "model": "gpt-4o-mini",
        "allowed_tools": ["file_read", "grep", "ls"],
        "description": "Fast codebase searcher."
    }
}
```

**Step 2: Update AgentConfig**
```python
# sage/config.py
class AgentConfig(BaseModel):
    # ...
    role: Optional[str] = None
```

**Step 3: Resolve Roles in Agent Initialization**
```python
# sage/agent.py (in _from_agent_config)
if config.role and config.role in ROLE_DEFAULTS:
    defaults = ROLE_DEFAULTS[config.role]
    if not config.model: config.model = defaults["model"]
    # Merge blocked_tools and allowed_tools with Phase 1 logic
```

**Verification:**
- Create agent with `role: consultant`.
- Verify `agent.tool_registry.get_schemas()` does not contain `shell`.

---

### Task 6: Dynamic Prompt Construction from Agent Metadata

**Files:**
- Modify: `sage/config.py` (Add `AgentPromptMetadata`)
- Create: `sage/prompts/dynamic_builder.py` (Prompt generation logic)
- Modify: `sage/agent.py` (Apply dynamic builder to system prompt)

**Step 1: Add Metadata to Config**
```python
# sage/config.py
class AgentPromptMetadata(BaseModel):
    cost: Literal["free", "cheap", "moderate", "expensive"] = "moderate"
    triggers: list[str] = Field(default_factory=list)
    use_when: list[str] = Field(default_factory=list)
    avoid_when: list[str] = Field(default_factory=list)

class AgentConfig(BaseModel):
    # ...
    prompt_metadata: AgentPromptMetadata = Field(default_factory=AgentPromptMetadata)
```

**Step 2: Implement Dynamic Builder**
```python
# sage/prompts/dynamic_builder.py
def build_delegation_table(subagents: Dict[str, "Agent"]) -> str:
    lines = ["| Agent | Cost | Triggers | Description |", "|-------|------|----------|-------------|"]
    for name, sub in subagents.items():
        meta = getattr(sub, "prompt_metadata", None)
        cost = meta.cost if meta else "moderate"
        triggers = ", ".join(meta.triggers) if meta else "None"
        lines.append(f"| {name} | {cost} | {triggers} | {sub.description} |")
    return "\n".join(lines)

def build_orchestrator_prompt(base_prompt: str, subagents: Dict[str, "Agent"]) -> str:
    table = build_delegation_table(subagents)
    return base_prompt.replace("{{DELEGATION_TABLE}}", table)
```

**Step 3: Wire Builder into Agent**
```python
# sage/agent.py (in __init__ or _pre_loop_setup)
if "{{DELEGATION_TABLE}}" in self._body:
    from sage.prompts.dynamic_builder import build_orchestrator_prompt
    self._body = build_orchestrator_prompt(self._body, self.subagents)
```

**Verification:**
- Create orchestrator with `{{DELEGATION_TABLE}}` in its body.
- Run agent, verify the system message contains a markdown table listing subagents.

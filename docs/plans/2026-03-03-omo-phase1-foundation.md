# Phase 1: Foundation Implementation Plan

**Goal:** Strengthen the core agent infrastructure with role-based tool restrictions, stateful delegations, and category-driven model routing.

**Architecture:**
- **Tool Restrictions:** Enforced at the `ToolRegistry` level to prevent execution and advertisement of blocked tools.
- **Session Continuity:** Leveraging `SessionManager` to persist and resume conversation history across `delegate()` calls.
- **Model Routing:** Extending `MainConfig` with `CategoryConfig` to allow explicit model overrides during delegation.

**Tech Stack:** Python 3.10+, Pydantic v2, LiteLLM, Pytest, Asyncio

---

### Task 1: Per-Agent Tool Restrictions (Role Enforcement)

**Files:**
- Modify: `sage/config.py` (Add `allowed_tools` and `blocked_tools` to `AgentConfig`)
- Modify: `sage/tools/registry.py` (Implement filtering in `execute()` and `get_schemas()`)
- Modify: `sage/agent.py` (Pass restrictions from config to registry)

**Step 1: Update AgentConfig schema**
Add restriction fields to `AgentConfig` in `sage/config.py`.

```python
# sage/config.py (~line 246)
class AgentConfig(BaseModel):
    # ... existing fields ...
    allowed_tools: list[str] | None = None
    blocked_tools: list[str] | None = None
```

**Step 2: Implement enforcement in ToolRegistry**
Add filtering logic to `ToolRegistry` in `sage/tools/registry.py`.

```python
# sage/tools/registry.py (~line 68)
class ToolRegistry:
    def __init__(self, default_timeout: float | None = None) -> None:
        # ... existing ...
        self._allowed_tools: set[str] | None = None
        self._blocked_tools: set[str] = set()

    def set_restrictions(self, allowed: list[str] | None = None, blocked: list[str] | None = None) -> None:
        """Set infrastructure-level tool restrictions."""
        self._allowed_tools = set(allowed) if allowed is not None else None
        self._blocked_tools = set(blocked) if blocked is not None else set()

    def get_schemas(self) -> list[ToolSchema]:
        """Return schemas for all registered tools, applying restrictions."""
        schemas = list(self._schemas.values())
        if self._allowed_tools is not None:
            schemas = [s for s in schemas if s.name in self._allowed_tools]
        if self._blocked_tools:
            schemas = [s for s in schemas if s.name not in self._blocked_tools]
        return schemas

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        # Pre-dispatch restriction check
        if self._allowed_tools is not None and name not in self._allowed_tools:
            raise SagePermissionError(f"Tool {name!r} is not in the allowlist for this agent.")
        if name in self._blocked_tools:
            raise SagePermissionError(f"Tool {name!r} is explicitly blocked for this agent.")

        # ... rest of execute() ...
```

**Step 3: Wire restriction logic in Agent**
Update `Agent._from_agent_config` in `sage/agent.py` to apply restrictions.

```python
# sage/agent.py (~line 338)
agent = cls(...)
# ...
if config.allowed_tools or config.blocked_tools:
    agent.tool_registry.set_restrictions(
        allowed=config.allowed_tools,
        blocked=config.blocked_tools
    )
```

**Verification:**
- `pytest tests/test_tools.py` passes.
- Test case: Create agent with `blocked_tools=["shell"]`. Verify `agent.tool_registry.get_schemas()` does not include shell and `execute("shell", ...)` raises `SagePermissionError`.

---

### Task 2: Session Continuity for Delegations

**Files:**
- Modify: `sage/agent.py` (Update `delegate` tool schema and `delegate()` implementation)
- Modify: `sage/coordination/session.py` (Ensure `SessionManager` is usable)

**Step 1: Update delegation tool registration**
Modify `_register_delegation_tools` in `sage/agent.py` to include `session_id`.

```python
# sage/agent.py (~line 938)
async def delegate(agent_name: str, task: str, session_id: str | None = None) -> str:
    return await agent_ref.delegate(agent_name, task, session_id=session_id)

schema = ToolSchema(
    name="delegate",
    # ...
    parameters={
        "type": "object",
        "properties": {
            "agent_name": { ... },
            "task": { ... },
            "session_id": {
                "type": "string",
                "description": "Optional session ID to resume a previous conversation with this subagent."
            },
        },
        "required": ["agent_name", "task"],
    },
)
```

**Step 2: Implement stateful delegation**
Update `Agent.delegate()` to handle session persistence.

```python
# sage/agent.py (~line 661)
async def delegate(self, subagent_name: str, task: str, session_id: str | None = None) -> str:
    # ... existing validation ...

    subagent = self.subagents[subagent_name]
    from sage.coordination.session import SessionManager

    # Simple singleton-like access or passed-down manager
    session_mgr = getattr(self, "_session_mgr", SessionManager())

    if session_id:
        session = session_mgr.get(session_id)
        if session:
            # Load history (excluding system messages which are rebuilt)
            subagent._conversation_history = [m for m in session.messages if m.role != "system"]

    # Run subagent
    result = await subagent.run(task)

    # Save back to session
    effective_sid = session_id or f"{subagent_name}_{int(time.time())}"
    session = session_mgr.create(subagent_name, session_id=effective_sid)
    session.messages = list(subagent._conversation_history)

    # Return formatted result with SID for next turn
    return f"[Session: {effective_sid}]\n{result}"
```

**Verification:**
- `pytest tests/test_agent.py -k "test_delegate"` passes.
- Test case: Delegate task A, get response with `[Session: xyz]`. Delegate task B using `session_id="xyz"`. Verify subagent's internal `messages` includes task A and its response.

---

### Task 3: Category-Based Model Routing

**Files:**
- Modify: `sage/config.py` (Add `CategoryConfig` and `CategoryOverrides`)
- Modify: `sage/main_config.py` (Update `MainConfig` to parse categories)
- Modify: `sage/agent.py` (Resolve category in `delegate()`)

**Step 1: Add Category models to config**
Define routing structures in `sage/config.py`.

```python
# sage/config.py (~line 97)
class CategoryConfig(BaseModel):
    model: str
    model_params: ModelParams = Field(default_factory=ModelParams)

# Update MainConfig in sage/main_config.py
class MainConfig(BaseModel):
    # ...
    categories: dict[str, CategoryConfig] = Field(default_factory=dict)
```

**Step 2: Update delegate tool with category support**
Add `category` to the schema in `sage/agent.py`.

```python
# sage/agent.py (~line 955)
"category": {
    "type": "string",
    "description": "Task category for model routing (e.g., 'quick', 'deep').",
    "enum": ["quick", "deep", "default"] # Dynamically populated if possible
}
```

**Step 3: Resolve model during delegation**
Update `Agent.delegate()` to apply category overrides.

```python
# sage/agent.py (~line 681)
async def delegate(self, subagent_name: str, task: str, session_id: str | None = None, category: str | None = None) -> str:
    subagent = self.subagents[subagent_name]

    # Apply category override if configured
    if category and hasattr(self, "_main_config"):
        cat_cfg = self._main_config.categories.get(category)
        if cat_cfg:
            logger.info("Routing delegation to %s using category %s (%s)", subagent_name, category, cat_cfg.model)
            subagent.model = cat_cfg.model
            # Re-initialize provider with new model/params
            from sage.providers.litellm_provider import LiteLLMProvider
            subagent.provider = LiteLLMProvider(cat_cfg.model, **cat_cfg.model_params.to_kwargs())

    # ... proceed with run ...
```

**Verification:**
- `pytest tests/test_main_config.py` passes for category parsing.
- Test case: Set `categories.quick.model = "gpt-4o-mini"`. Delegate with `category="quick"`. Verify subagent's `provider.model` matches.

---

### Summary of Changes

| Task | Core Changes | Primary Files |
|------|--------------|---------------|
| 1    | Tool allowlist/blocklist enforcement | `sage/config.py`, `sage/tools/registry.py` |
| 2    | Stateful delegation with `session_id` | `sage/agent.py`, `sage/coordination/session.py` |
| 3    | Model routing via `category` | `sage/main_config.py`, `sage/agent.py` |

# Lazy Skill Loading Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace eager full-content skill injection with two-phase loading: frontmatter catalog in system prompt, full content via `use_skill` tool on demand.

**Architecture:** Closure-based `use_skill` tool auto-registered on the Agent when skills are present, following the same pattern as `_register_memory_tools()`. System prompt emits compact catalog only. Loaded skills tracked with a `set()` for idempotency.

**Tech Stack:** Python, Pydantic, pytest, async

---

### Task 1: Update Existing Skill Tests for New Catalog Behavior

**Files:**
- Modify: `tests/test_agent.py:795-863` (TestAgentSkills class)

**Step 1: Update `test_skill_injected_into_system_message`**

This test currently asserts full content appears in the system message. Change it to assert the catalog format instead.

```python
@pytest.mark.asyncio
async def test_skill_catalog_in_system_message(self) -> None:
    """Skills appear as a compact catalog in the system message, not full content."""
    from sage.skills.loader import Skill

    skill = Skill(
        name="my-skill",
        description="Does something useful",
        content="Always start with step 1.",
    )
    provider = MockProvider([_text_result("ok")])
    agent = Agent(
        name="test",
        model="m",
        body="Base body.",
        skills=[skill],
        provider=provider,
    )

    await agent.run("hi")

    messages = provider.call_args[0]["messages"]
    system_msg = next(m for m in messages if m.role == "system")
    assert "## Available Skills" in system_msg.content
    assert "**my-skill**: Does something useful" in system_msg.content
    # Full content must NOT be in system message.
    assert "Always start with step 1." not in system_msg.content
```

**Step 2: Update `test_multiple_skills_all_injected`**

```python
@pytest.mark.asyncio
async def test_multiple_skills_catalog_entries(self) -> None:
    """All skills appear as catalog entries in the system message."""
    from sage.skills.loader import Skill

    skills = [
        Skill(name="skill-a", description="Desc A", content="Content A."),
        Skill(name="skill-b", description="Desc B", content="Content B."),
    ]
    provider = MockProvider([_text_result("ok")])
    agent = Agent(name="test", model="m", skills=skills, provider=provider)

    await agent.run("hi")

    messages = provider.call_args[0]["messages"]
    system_msg = next(m for m in messages if m.role == "system")
    assert "**skill-a**: Desc A" in system_msg.content
    assert "**skill-b**: Desc B" in system_msg.content
    # Full content must NOT be in system message.
    assert "Content A." not in system_msg.content
    assert "Content B." not in system_msg.content
```

**Step 3: Update `test_skills_appended_after_persona`**

```python
@pytest.mark.asyncio
async def test_skill_catalog_appended_after_persona(self) -> None:
    """Skill catalog appears after body content in the system message."""
    from sage.skills.loader import Skill

    skill = Skill(name="s", description="desc", content="Skill content.")
    provider = MockProvider([_text_result("ok")])
    agent = Agent(
        name="test",
        model="m",
        body="My body.",
        skills=[skill],
        provider=provider,
    )

    await agent.run("hi")

    messages = provider.call_args[0]["messages"]
    system_msg = next(m for m in messages if m.role == "system")
    body_pos = system_msg.content.index("My body.")
    catalog_pos = system_msg.content.index("## Available Skills")
    assert body_pos < catalog_pos
```

**Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_agent.py::TestAgentSkills::test_skill_catalog_in_system_message tests/test_agent.py::TestAgentSkills::test_multiple_skills_catalog_entries tests/test_agent.py::TestAgentSkills::test_skill_catalog_appended_after_persona -v`
Expected: FAIL — the current code still injects full content.

**Step 5: Commit**

```bash
git add tests/test_agent.py
git commit -m "test: update skill tests to expect catalog-only system prompt"
```

---

### Task 2: Write Tests for `use_skill` Tool

**Files:**
- Modify: `tests/test_agent.py` (add new tests in TestAgentSkills class)

**Step 1: Write test for `use_skill` returning content on first call**

```python
@pytest.mark.asyncio
async def test_use_skill_returns_content(self) -> None:
    """use_skill tool returns the full skill content on first call."""
    from sage.skills.loader import Skill

    skill = Skill(name="my-skill", description="desc", content="Full instructions here.")
    provider = MockProvider([
        _tool_call_result([ToolCall(id="1", name="use_skill", arguments={"name": "my-skill"})]),
        _text_result("done"),
    ])
    agent = Agent(name="test", model="m", skills=[skill], provider=provider)

    await agent.run("hi")

    # The second call should have the tool result in conversation history.
    second_call_messages = provider.call_args[1]["messages"]
    tool_msg = next(m for m in second_call_messages if m.role == "tool")
    assert tool_msg.content == "Full instructions here."
```

**Step 2: Write test for `use_skill` returning "already loaded" on repeat call**

```python
@pytest.mark.asyncio
async def test_use_skill_already_loaded(self) -> None:
    """use_skill tool returns short message on repeat call for same skill."""
    from sage.skills.loader import Skill

    skill = Skill(name="my-skill", description="desc", content="Full instructions.")
    provider = MockProvider([
        _tool_call_result([ToolCall(id="1", name="use_skill", arguments={"name": "my-skill"})]),
        _tool_call_result([ToolCall(id="2", name="use_skill", arguments={"name": "my-skill"})]),
        _text_result("done"),
    ])
    agent = Agent(name="test", model="m", skills=[skill], provider=provider)

    await agent.run("hi")

    third_call_messages = provider.call_args[2]["messages"]
    tool_msgs = [m for m in third_call_messages if m.role == "tool"]
    last_tool_msg = tool_msgs[-1]
    assert "already loaded" in last_tool_msg.content
```

**Step 3: Write test for `use_skill` with unknown skill name**

```python
@pytest.mark.asyncio
async def test_use_skill_unknown_name(self) -> None:
    """use_skill tool returns error with available names for unknown skill."""
    from sage.skills.loader import Skill

    skill = Skill(name="real-skill", description="desc", content="Content.")
    provider = MockProvider([
        _tool_call_result([ToolCall(id="1", name="use_skill", arguments={"name": "fake-skill"})]),
        _text_result("done"),
    ])
    agent = Agent(name="test", model="m", skills=[skill], provider=provider)

    await agent.run("hi")

    second_call_messages = provider.call_args[1]["messages"]
    tool_msg = next(m for m in second_call_messages if m.role == "tool")
    assert "Unknown skill" in tool_msg.content
    assert "real-skill" in tool_msg.content
```

**Step 4: Write test that `use_skill` tool is registered when skills exist**

```python
def test_use_skill_tool_registered_when_skills_present(self) -> None:
    """use_skill tool is auto-registered when agent has skills."""
    from sage.skills.loader import Skill

    skill = Skill(name="s", content="c")
    provider = MockProvider([])
    agent = Agent(name="test", model="m", skills=[skill], provider=provider)
    assert "use_skill" in agent.tool_registry._tools

def test_use_skill_tool_not_registered_when_no_skills(self) -> None:
    """use_skill tool is NOT registered when agent has no skills."""
    provider = MockProvider([])
    agent = Agent(name="test", model="m", provider=provider)
    assert "use_skill" not in agent.tool_registry._tools
```

**Step 5: Run tests to verify they fail**

Run: `uv run pytest tests/test_agent.py::TestAgentSkills::test_use_skill_returns_content tests/test_agent.py::TestAgentSkills::test_use_skill_already_loaded tests/test_agent.py::TestAgentSkills::test_use_skill_unknown_name tests/test_agent.py::TestAgentSkills::test_use_skill_tool_registered_when_skills_present tests/test_agent.py::TestAgentSkills::test_use_skill_tool_not_registered_when_no_skills -v`
Expected: FAIL — `use_skill` tool does not exist yet.

**Step 6: Commit**

```bash
git add tests/test_agent.py
git commit -m "test: add use_skill tool tests for lazy skill loading"
```

---

### Task 3: Implement `_register_skill_tool()` on Agent

**Files:**
- Modify: `sage/agent.py:173-176` (`__init__`, add registration call)
- Modify: `sage/agent.py:858` (add new method after `_register_memory_tools`)

**Step 1: Add `_register_skill_tool()` method**

Insert after `_register_memory_tools()` (after line 894 in `sage/agent.py`):

```python
def _register_skill_tool(self) -> None:
    """Register ``use_skill`` tool when the agent has skills.

    The tool returns a skill's full markdown content on first invocation
    and a short "already loaded" message on subsequent calls for the same
    skill.  This implements two-phase skill loading: only the lightweight
    catalog (name + description) lives in the system prompt; full content
    is loaded on demand.
    """
    if not self.skills:
        return

    from sage.tools.decorator import tool as _tool

    skill_map = {s.name: s for s in self.skills}
    loaded: set[str] = set()

    @_tool
    async def use_skill(name: str) -> str:
        """Load a skill's full instructions by name.

        Use this when a task matches one of the available skills listed
        in your system prompt.  Returns the skill's complete markdown
        instructions for you to follow.
        """
        if name not in skill_map:
            available = ", ".join(sorted(skill_map))
            return f"Unknown skill '{name}'. Available: {available}"
        if name in loaded:
            return f"Skill '{name}' is already loaded in this conversation."
        loaded.add(name)
        skill = skill_map[name]
        return skill.content

    self.tool_registry.register(use_skill)
```

**Step 2: Wire it in `__init__`**

After the delegation tool registration (line 175), add:

```python
# Auto-register delegation tools when subagents are present.
if self.subagents:
    self._register_delegation_tools()

# Auto-register skill tool when skills are present.
if self.skills:
    self._register_skill_tool()
```

**Step 3: Run `use_skill`-specific tests to verify they pass**

Run: `uv run pytest tests/test_agent.py::TestAgentSkills::test_use_skill_returns_content tests/test_agent.py::TestAgentSkills::test_use_skill_already_loaded tests/test_agent.py::TestAgentSkills::test_use_skill_unknown_name tests/test_agent.py::TestAgentSkills::test_use_skill_tool_registered_when_skills_present tests/test_agent.py::TestAgentSkills::test_use_skill_tool_not_registered_when_no_skills -v`
Expected: PASS for registration and tool behavior tests; catalog tests still FAIL (not implemented yet).

**Step 4: Commit**

```bash
git add sage/agent.py
git commit -m "feat: add use_skill tool for on-demand skill loading"
```

---

### Task 4: Change `_build_messages()` to Emit Catalog Only

**Files:**
- Modify: `sage/agent.py:907-917` (`_build_messages` method)

**Step 1: Replace full content injection with catalog block**

Change lines 907-917 from:

```python
# System message from description/body + skills.
system_parts: list[str] = []
if self._body:
    system_parts.append(self._body)
for skill in self.skills:
    header = f"## Skill: {skill.name}"
    if skill.description:
        header += f"\n_{skill.description}_"
    system_parts.append(f"{header}\n\n{skill.content}")
```

To:

```python
# System message from description/body + skill catalog.
system_parts: list[str] = []
if self._body:
    system_parts.append(self._body)
if self.skills:
    catalog_lines = [
        "## Available Skills",
        "Use the `use_skill` tool to load a skill's full instructions.",
        "",
    ]
    for skill in self.skills:
        line = f"- **{skill.name}**"
        if skill.description:
            line += f": {skill.description}"
        catalog_lines.append(line)
    system_parts.append("\n".join(catalog_lines))
```

**Step 2: Run catalog tests to verify they pass**

Run: `uv run pytest tests/test_agent.py::TestAgentSkills::test_skill_catalog_in_system_message tests/test_agent.py::TestAgentSkills::test_multiple_skills_catalog_entries tests/test_agent.py::TestAgentSkills::test_skill_catalog_appended_after_persona -v`
Expected: PASS

**Step 3: Run full TestAgentSkills class**

Run: `uv run pytest tests/test_agent.py::TestAgentSkills -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add sage/agent.py
git commit -m "feat: emit skill catalog in system prompt instead of full content"
```

---

### Task 5: Remove Skill-Name Matching from `_execute_tool_calls()`

**Files:**
- Modify: `sage/agent.py:700-720` (`_execute_tool_calls` method)

**Step 1: Simplify `_safe_execute` logging**

Replace lines 700-720:

```python
# Build a quick lookup for skill-name matching.
skill_names = {s.name for s in self.skills}

async def _safe_execute(tc: ToolCall) -> tuple[str, str]:
    # Log whether this tool dispatch is skill-driven.
    if tc.name == "delegate":
        # Delegation is logged inside delegate(); skip here.
        pass
    elif tc.name == "shell" and skill_names:
        cmd = (tc.arguments or {}).get("command", "")
        matched = [sn for sn in skill_names if sn in cmd]
        if matched:
            logger.debug(
                "Delegating to skill '%s' via shell: %s",
                matched[0],
                cmd[:120],
            )
        else:
            logger.debug("Executing tool '%s': %s", tc.name, str(tc.arguments)[:120])
    else:
        logger.debug("Executing tool '%s': %s", tc.name, str(tc.arguments)[:120])
```

With:

```python
async def _safe_execute(tc: ToolCall) -> tuple[str, str]:
    if tc.name != "delegate":
        logger.debug("Executing tool '%s': %s", tc.name, str(tc.arguments)[:120])
```

**Step 2: Run full test suite**

Run: `uv run pytest tests/test_agent.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add sage/agent.py
git commit -m "refactor: remove skill-name matching heuristic from tool dispatch"
```

---

### Task 6: Run Full Test Suite and Verify Examples

**Files:** None (verification only)

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS

**Step 2: Run type checker**

Run: `uv run mypy sage`
Expected: No new errors

**Step 3: Run linter**

Run: `uv run ruff check sage tests --fix && uv run ruff format sage tests`
Expected: Clean

**Step 4: Run `make run-examples` to verify the original issue is fixed**

Run: `make run-examples`
Expected: `simple_agent` example no longer fails with ContextWindowExceededError. The system prompt is ~3K tokens instead of ~155K.

**Step 5: Commit any lint/format fixes**

```bash
git add -u
git commit -m "style: lint and format fixes for lazy skill loading"
```

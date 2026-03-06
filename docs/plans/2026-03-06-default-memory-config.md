# Default Memory Configuration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow `[defaults.memory]` in `config.toml` so all agents share a memory configuration, with per-agent `[agents.<name>.memory]` and frontmatter `memory:` deep-merging on top.

**Architecture:** Add `memory` to `ConfigOverrides` (removing the redundant definition from `AgentOverrides`), then add a `_merge_memory` helper that builds the merged memory dict using `model_fields_set` to distinguish explicitly-written fields from Pydantic defaults. `merge_agent_config` is updated to pop `memory` from each tier dict and route it through the helper instead of the general shallow update.

**Tech Stack:** Python 3.12+, Pydantic v2 (`model_fields_set`), `tomllib`

---

### Task 1: Move `memory` to `ConfigOverrides` (TDD)

**Files:**
- Modify: `sage/main_config.py:45-66`
- Test: `tests/test_main_config.py`

---

**Step 1: Write the failing tests**

Add two new test methods to `TestConfigOverrides` in `tests/test_main_config.py` (insert after the existing `test_extra_fields_rejected` method). Also add one TOML-parsing integration test at the bottom of `TestLoadMainConfig`:

```python
# Add to class TestConfigOverrides:

    def test_memory_field_default_none(self) -> None:
        overrides = ConfigOverrides()
        assert overrides.memory is None

    def test_memory_field_accepts_memory_config(self) -> None:
        overrides = ConfigOverrides(memory={"backend": "sqlite", "path": "mem.db"})  # type: ignore[arg-type]
        assert overrides.memory is not None
        assert overrides.memory.backend == "sqlite"
        assert overrides.memory.path == "mem.db"
```

```python
# Add to class TestLoadMainConfig:

    def test_defaults_memory_parsed_from_toml(self, tmp_path: Path) -> None:
        toml_path = _write_toml(
            tmp_path / "config.toml",
            '[defaults.memory]\nembedding = "ollama/nomic-embed-text"\n',
        )
        cfg = load_main_config(toml_path)
        assert cfg is not None
        assert cfg.defaults.memory is not None
        assert cfg.defaults.memory.embedding == "ollama/nomic-embed-text"
```

Also update the existing `test_all_none_by_default` in `TestConfigOverrides` to include `memory`:

```python
    def test_all_none_by_default(self) -> None:
        overrides = ConfigOverrides()
        assert overrides.model is None
        assert overrides.model_params is None
        assert overrides.max_turns is None
        assert overrides.permission is None
        assert overrides.context is None
        assert overrides.extensions is None
        assert overrides.mcp_servers is None
        assert overrides.memory is None   # add this line
```

**Step 2: Run tests to verify they fail**

```bash
cd /home/sachoi/sagebynature/sage-agent && pytest tests/test_main_config.py::TestConfigOverrides::test_memory_field_default_none tests/test_main_config.py::TestConfigOverrides::test_memory_field_accepts_memory_config tests/test_main_config.py::TestLoadMainConfig::test_defaults_memory_parsed_from_toml -v
```

Expected: `FAILED` — `ConfigOverrides` rejects `memory` with `extra="forbid"` and `test_defaults_memory_parsed_from_toml` raises `ConfigError: Invalid main config`.

---

**Step 3: Implement the change**

In `sage/main_config.py`:

1. Add `memory` to `ConfigOverrides` (after `planning` on line 59):

```python
class ConfigOverrides(BaseModel):
    """Fields that can appear in defaults or per-agent overrides."""

    model_config = ConfigDict(extra="forbid")

    model: str | None = None
    model_params: ModelParams | None = None
    max_turns: int | None = None
    max_depth: int | None = None
    permission: Permission | None = None
    shell_dangerous_patterns: list[str] | None = None
    context: ContextConfig | None = None
    extensions: list[str] | None = None
    mcp_servers: dict[str, MCPServerConfig] | None = None
    planning: PlanningConfig | None = None
    memory: MemoryConfig | None = None   # new
```

2. Remove the now-redundant `memory` field from `AgentOverrides` and update its docstring:

```python
class AgentOverrides(ConfigOverrides):
    """Per-agent overrides — adds skills allowlist."""

    skills: list[str] | None = None
```

**Step 4: Run tests to verify they pass**

```bash
cd /home/sachoi/sagebynature/sage-agent && pytest tests/test_main_config.py::TestConfigOverrides tests/test_main_config.py::TestAgentOverrides tests/test_main_config.py::TestLoadMainConfig -v
```

Expected: all pass. Confirm `TestAgentOverrides::test_memory_field` still passes (memory is now inherited from `ConfigOverrides`).

Run the full test suite to confirm no regressions:

```bash
cd /home/sachoi/sagebynature/sage-agent && pytest tests/ -q --ignore=tests/test_tracing.py 2>&1 | tail -5
```

Expected: same pass count as before, no new failures.

**Step 5: Commit**

```bash
cd /home/sachoi/sagebynature/sage-agent
git add sage/main_config.py tests/test_main_config.py
git commit -m "feat(config): move memory field to ConfigOverrides to support [defaults.memory]"
```

---

### Task 2: Deep-merge memory in `merge_agent_config` (TDD)

**Files:**
- Modify: `sage/main_config.py:190-226`
- Test: `tests/test_main_config.py`

---

**Step 1: Write the failing tests**

Append a new `TestMergeAgentConfigMemory` class to `tests/test_main_config.py`:

```python
# ---------------------------------------------------------------------------
# merge_agent_config — memory deep-merge
# ---------------------------------------------------------------------------


class TestMergeAgentConfigMemory:
    def test_no_memory_anywhere(self) -> None:
        """memory key absent from merged dict when no tier configures it."""
        central = MainConfig(defaults=ConfigOverrides(model="gpt-4o"))
        metadata: dict[str, object] = {"name": "agent", "model": "gpt-4o"}
        merged = merge_agent_config(metadata, central)
        assert "memory" not in merged

    def test_default_memory_applied(self) -> None:
        """[defaults.memory] fields appear in merged result with MemoryConfig defaults filled in."""
        central = MainConfig(
            defaults=ConfigOverrides(
                model="gpt-4o",
                memory={"embedding": "ollama/nomic-embed-text"},  # type: ignore[arg-type]
            )
        )
        metadata: dict[str, object] = {"name": "agent"}
        merged = merge_agent_config(metadata, central)
        assert merged["memory"]["embedding"] == "ollama/nomic-embed-text"
        assert merged["memory"]["backend"] == "sqlite"   # MemoryConfig default

    def test_agent_memory_deep_merges_with_default(self) -> None:
        """[agents.x.memory] fields override defaults; unset agent fields inherit defaults."""
        central = MainConfig(
            defaults=ConfigOverrides(
                model="gpt-4o",
                memory={"embedding": "ollama/nomic-embed-text"},  # type: ignore[arg-type]
            ),
            agents={
                "researcher": AgentOverrides(
                    memory={"path": "researcher.db"},  # type: ignore[arg-type]
                )
            },
        )
        metadata: dict[str, object] = {"name": "researcher"}
        merged = merge_agent_config(metadata, central, "researcher")
        assert merged["memory"]["path"] == "researcher.db"           # agent wins
        assert merged["memory"]["embedding"] == "ollama/nomic-embed-text"  # default inherited

    def test_frontmatter_memory_wins(self) -> None:
        """Frontmatter memory fields take highest precedence."""
        central = MainConfig(
            defaults=ConfigOverrides(
                model="gpt-4o",
                memory={"embedding": "ollama/nomic-embed-text", "path": "default.db"},  # type: ignore[arg-type]
            ),
            agents={
                "researcher": AgentOverrides(
                    memory={"path": "researcher.db"},  # type: ignore[arg-type]
                )
            },
        )
        metadata: dict[str, object] = {
            "name": "researcher",
            "memory": {"path": "frontmatter.db"},
        }
        merged = merge_agent_config(metadata, central, "researcher")
        assert merged["memory"]["path"] == "frontmatter.db"               # frontmatter wins
        assert merged["memory"]["embedding"] == "ollama/nomic-embed-text"  # default inherited

    def test_no_default_memory_agent_memory_only(self) -> None:
        """No [defaults.memory]; agent memory still applied with MemoryConfig defaults."""
        central = MainConfig(
            defaults=ConfigOverrides(model="gpt-4o"),
            agents={
                "researcher": AgentOverrides(
                    memory={"path": "researcher.db"},  # type: ignore[arg-type]
                )
            },
        )
        metadata: dict[str, object] = {"name": "researcher"}
        merged = merge_agent_config(metadata, central, "researcher")
        assert merged["memory"]["path"] == "researcher.db"
        assert merged["memory"]["embedding"] == "text-embedding-3-large"  # MemoryConfig default
```

**Step 2: Run tests to verify they fail**

```bash
cd /home/sachoi/sagebynature/sage-agent && pytest tests/test_main_config.py::TestMergeAgentConfigMemory -v
```

Expected: all 5 tests `FAILED` — `[defaults.memory]` is currently ignored by `merge_agent_config`, so merged memory dict is wrong or absent.

---

**Step 3: Implement `_merge_memory` and update `merge_agent_config`**

In `sage/main_config.py`, add the `_merge_memory` helper **before** `merge_agent_config` (insert it around line 190). Then update `merge_agent_config` to use it.

**New helper function (insert before `merge_agent_config`):**

```python
def _merge_memory(
    defaults: ConfigOverrides,
    agent_overrides: AgentOverrides | None,
    frontmatter: dict[str, Any],
) -> dict[str, Any] | None:
    """Deep-merge memory config from three tiers.

    Returns ``None`` when no tier provides any memory config (preserving
    the existing opt-in behaviour for agents that don't use memory).

    Uses ``model_fields_set`` to apply only fields explicitly written by
    the user at each tier, avoiding accidental propagation of Pydantic
    field defaults from one tier overriding values set at a lower tier.
    """
    has_any = (
        defaults.memory is not None
        or (agent_overrides is not None and agent_overrides.memory is not None)
        or "memory" in frontmatter
    )
    if not has_any:
        return None

    # Start with all MemoryConfig baseline defaults
    merged: dict[str, Any] = MemoryConfig().model_dump()

    # Apply only explicitly-set fields from [defaults.memory]
    if defaults.memory is not None:
        explicitly_set = defaults.memory.model_dump(include=defaults.memory.model_fields_set)
        merged.update(explicitly_set)

    # Apply only explicitly-set fields from [agents.x.memory]
    if agent_overrides is not None and agent_overrides.memory is not None:
        explicitly_set = agent_overrides.memory.model_dump(
            include=agent_overrides.memory.model_fields_set
        )
        merged.update(explicitly_set)

    # Apply all frontmatter memory fields (highest priority, raw dict)
    if "memory" in frontmatter:
        merged.update(frontmatter["memory"])

    return merged
```

**Updated `merge_agent_config` (replace the entire function):**

```python
def merge_agent_config(
    metadata: dict[str, Any],
    central: MainConfig | None,
    agent_name: str | None = None,
) -> dict[str, Any]:
    """Merge main config defaults and agent overrides into frontmatter metadata.

    Layering (lowest to highest priority):
      1. ``central.defaults``
      2. ``central.agents[agent_name]``  (if present)
      3. *metadata* (frontmatter values)

    Most nested objects use top-level replacement semantics (e.g.
    ``model_params`` is replaced wholesale).  ``memory`` is the exception:
    it is deep-merged field-by-field so individual fields can be overridden
    at each tier without losing fields set at a lower tier.
    """
    if central is None:
        return metadata

    effective_skills: list[str] | None = getattr(central.defaults, "skills", None)
    agent_ovr = central.agents.get(agent_name) if agent_name else None

    # Deep-merge memory separately before the general shallow merge
    memory_merged = _merge_memory(central.defaults, agent_ovr, metadata)

    # Start with defaults (only explicitly-set fields), excluding memory
    merged: dict[str, Any] = central.defaults.model_dump(exclude_none=True)
    merged.pop("memory", None)

    # Layer agent-specific overrides (excluding memory)
    if agent_name and agent_name in central.agents:
        if central.agents[agent_name].skills is not None:
            effective_skills = central.agents[agent_name].skills
        agent_overrides = central.agents[agent_name].model_dump(exclude_none=True)
        agent_overrides.pop("memory", None)
        merged.update(agent_overrides)

    # Layer frontmatter values (excluding memory — handled above)
    merged.update({k: v for k, v in metadata.items() if k != "memory"})

    # Re-attach deep-merged memory (or omit if no tier configured it)
    if memory_merged is not None:
        merged["memory"] = memory_merged

    if effective_skills is not None:
        merged["skills"] = effective_skills

    return merged
```

**Step 4: Run tests to verify they pass**

```bash
cd /home/sachoi/sagebynature/sage-agent && pytest tests/test_main_config.py::TestMergeAgentConfigMemory -v
```

Expected: all 5 tests PASS.

Run the full `test_main_config.py` suite to confirm no regressions:

```bash
cd /home/sachoi/sagebynature/sage-agent && pytest tests/test_main_config.py -v
```

Expected: all pass.

Run the full project test suite:

```bash
cd /home/sachoi/sagebynature/sage-agent && pytest tests/ -q --ignore=tests/test_tracing.py 2>&1 | tail -5
```

Expected: same pass count as before, no new failures.

**Step 5: Commit**

```bash
cd /home/sachoi/sagebynature/sage-agent
git add sage/main_config.py tests/test_main_config.py
git commit -m "feat(config): deep-merge memory config across defaults, agent overrides, and frontmatter"
```

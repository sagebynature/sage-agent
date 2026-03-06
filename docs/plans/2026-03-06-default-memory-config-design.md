# Default Memory Configuration Design

**Date:** 2026-03-06
**Status:** Approved

## Summary

Allow `[defaults.memory]` in `config.toml` so a single memory configuration applies to all agents, while per-agent `[agents.<name>.memory]` sections and agent frontmatter can still override individual fields. Overrides deep-merge rather than replace.

## Architecture

All changes are in `sage/main_config.py`.

### 1. Add `memory` to `ConfigOverrides`

```python
class ConfigOverrides(BaseModel):
    ...
    memory: MemoryConfig | None = None   # new
```

This makes `[defaults.memory]` a valid TOML section. Previously it was rejected by `extra="forbid"`.

### 2. New helper: `_merge_memory`

Builds the merged memory dict from three tiers, using Pydantic's `model_fields_set` to distinguish explicitly-written fields from Pydantic defaults:

```
MemoryConfig() baseline defaults
  ← [defaults.memory]       (only fields in model_fields_set)
  ← [agents.x.memory]       (only fields in model_fields_set)
  ← frontmatter memory dict (all fields, as today)
```

Returns `None` if no tier provides any memory config, preserving the opt-in behaviour.

### 3. Update `merge_agent_config`

Before the general `merged.update()`, pop `memory` from all tier dicts and route through `_merge_memory`. The general shallow merge never touches `memory`, preventing accidental full replacement.

### Configuration example

```toml
[defaults.memory]
embedding = "ollama/nomic-embed-text"
backend = "sqlite"

[agents.researcher.memory]
path = "researcher.db"   # inherits embedding = "ollama/nomic-embed-text" from defaults
```

Merge precedence (highest wins per field): frontmatter > `[agents.x.memory]` > `[defaults.memory]` > `MemoryConfig` Pydantic defaults.

## Error Handling

No new error handling required. `MemoryConfig`'s existing Pydantic validation (`extra="forbid"`, `Literal` constraints) catches invalid fields or values at parse time, before any merge logic runs. Behaviour is identical to today's per-agent memory validation.

## Testing

New tests in `tests/test_main_config.py`:

- `test_default_memory_applied` — `[defaults.memory]` only; agent has no memory section; merged config has the default memory fields
- `test_agent_memory_overrides_default` — both `[defaults.memory]` and `[agents.x.memory]` set; agent-specific fields win, unset agent fields inherit from defaults
- `test_frontmatter_memory_wins` — all three tiers set; frontmatter fields take highest precedence
- `test_no_default_memory_agent_memory_only` — no `[defaults.memory]`, agent has `[agents.x.memory]`; existing behaviour unchanged
- `test_no_memory_anywhere` — neither defaults nor agent set memory; `config.memory is None` preserved

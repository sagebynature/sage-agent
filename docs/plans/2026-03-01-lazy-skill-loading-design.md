# Lazy Skill Loading Design

**Date:** 2026-03-01
**Status:** Approved

## Problem

Skills are loaded eagerly — the full markdown body of every skill is injected
into the system prompt on every turn.  With 105 skills in `~/.claude/skills/`,
this produces ~155K tokens in the system message, exceeding gpt-4o's 128K
context window and making `make run-examples` fail on the simplest agent.

## Design

Two-phase skill loading: frontmatter-only catalog in the system prompt,
full content loaded on-demand via a `use_skill` tool.

### Phase 1 — Catalog in System Prompt

`_build_messages()` emits a compact skill catalog instead of full content:

```
## Available Skills
Use the `use_skill` tool to load a skill's full instructions.

- **python-pro**: Master Python 3.12+ with modern features...
- **react-patterns**: Modern React patterns and principles...
```

Cost: ~3K tokens for 105 skills (down from ~155K).

### Phase 2 — On-Demand Loading via `use_skill` Tool

A new `use_skill(name: str)` tool is auto-registered when the agent has skills.
The LLM calls it when a task matches a skill from the catalog.

- First call: returns the skill's full markdown content as a tool result
- Repeat call: returns `"Skill '{name}' is already loaded in this conversation."`
- Unknown name: returns error with list of available skill names

### Implementation — Closure on Agent

`_register_skill_tool()` follows the same pattern as `_register_memory_tools()`:
a closure capturing `skill_map` (dict by name) and `loaded` (set of names).
Called from `__init__` when `self.skills` is non-empty, same as delegation tools.

### Skill-Name Matching Removal

The heuristic in `_execute_tool_calls()` that checked if shell commands
contained skill names is removed.  With explicit `use_skill` calls the intent
is clear from the conversation flow.

## Changes

| File | Change |
|---|---|
| `sage/agent.py` `__init__` | Add `_register_skill_tool()` call |
| `sage/agent.py` `_register_skill_tool()` | New closure-based tool method |
| `sage/agent.py` `_build_messages()` | Catalog-only skill injection |
| `sage/agent.py` `_execute_tool_calls()` | Remove skill-name matching |

### Not Changed

- `sage/skills/loader.py` — Skill model, loading, filtering unchanged
- `sage/config.py` — `skills: list[str] | None` semantics unchanged (`None` = all)
- `sage/tools/registry.py` — no new category (auto-registered like `delegate`)
- Example AGENTS.md files — work as-is

## Token Budget

| Scenario (105 skills) | Before | After |
|---|---|---|
| System prompt | ~155K tokens | ~3K tokens |
| Per skill loaded | 0 (already in prompt) | ~1.5K tokens (tool result) |
| Typical session (2-3 skills used) | ~155K | ~6K |

## Test Plan

- `_build_messages()` emits catalog, not full content
- `use_skill` returns content on first call
- `use_skill` returns "already loaded" on second call
- `use_skill` returns error for unknown skill name
- Skill-name matching logic removed from `_safe_execute`

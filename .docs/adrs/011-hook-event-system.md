# ADR-011: Hook / Event System

## Status
Accepted

## Context

As Sage grew to support credential scrubbing, query-based model routing, bail-out retry, and automatic memory injection, each feature needed to tap into the same lifecycle points in `Agent.run()` — before the LLM call, after tool execution, after compaction, etc.

The naive approach of adding conditional branches directly to `agent.py` had three problems:

1. **Coupling**: Every new feature dirtied the core run loop.
2. **Composability**: Two features touching the same point (e.g., credential scrubbing *and* query routing both intercepting `PRE_LLM_CALL`) required explicit sequencing code.
3. **Testability**: Features embedded in the monolithic run loop are hard to unit-test in isolation.

## Decision

### `HookEvent` enum (`sage/hooks/base.py`)

A `str` enum naming every interception point in the agent lifecycle:

```
PRE_LLM_CALL / POST_LLM_CALL
PRE_TOOL_EXECUTE / POST_TOOL_EXECUTE
PRE_COMPACTION / POST_COMPACTION
PRE_MEMORY_RECALL / POST_MEMORY_STORE
ON_DELEGATION
ON_COMPACTION
```

### `HookRegistry` (`sage/hooks/registry.py`)

Central registry with two emission modes:

| Mode | Method | Handler contract | Execution |
|------|--------|-----------------|-----------|
| **Void** | `emit_void(event, data)` | `async (event, data) -> None` | All handlers in parallel (`asyncio.gather`) |
| **Modifying** | `emit_modifying(event, data)` | `async (event, data) -> dict \| None` | Sequential; each handler receives prior output |

Returning `None` from a modifying handler means "no change — pass data through unchanged."

All exceptions from any handler are caught, logged at `DEBUG` level, and swallowed. A hook error never crashes the agent run.

### Agent integration

`Agent.__init__` accepts an optional `hook_registry: HookRegistry | None` parameter. When omitted, a fresh empty registry is created so call sites are unconditional — no `if self._hook_registry` guards anywhere in the run loop.

A private `_emit(event, data)` helper wraps `emit_void()` with the same swallow-on-error contract, keeping call sites in the run loop to a single line.

### Built-in hooks (factory pattern)

Each built-in hook is a factory function returning a handler closure:

| Module | Factory | Event | Mode |
|--------|---------|-------|------|
| `credential_scrubber` | `make_credential_scrubber_hook()` | `POST_TOOL_EXECUTE` | void |
| `query_classifier` | `make_query_classifier()` | `PRE_LLM_CALL` | modifying |
| `follow_through` | `make_follow_through_hook()` | `POST_LLM_CALL` | modifying |
| `auto_memory` | `make_auto_memory_hook()` | `PRE_LLM_CALL` | void |

Factories receive configuration at construction time (via `AgentConfig` sub-models) and capture it in their closure, keeping registration and configuration separate from the registry mechanism itself.

### Config wiring (`_build_hook_registry`)

A module-level function `_build_hook_registry(config, memory)` in `sage/agent.py` reads the new `AgentConfig` fields (`credential_scrubbing`, `query_classification`, `follow_through`, and `memory.auto_load`) and registers the corresponding built-in hooks. Called from `_from_agent_config()` during agent construction.

## Consequences

**Positive:**
- **Zero coupling**: Adding a new lifecycle hook requires no changes to `agent.py` beyond a single `_emit()` call at the new point.
- **Composability**: Multiple handlers on the same event coexist without conflict. Void handlers run in parallel; modifying handlers chain deterministically.
- **Resilience**: Hook errors can never abort an agent run.
- **Testability**: Each built-in hook is a pure async function testable in complete isolation from the agent.
- **Config-driven**: Built-in hooks are activated entirely through frontmatter — no Python code required from users.

**Negative:**
- **Modifying hooks are sequential**: Parallel mutation would require a merge strategy; sequential is simpler and predictable but serializes execution.
- **No priority ordering for void hooks**: Handlers fire in registration order (not configurable). This is rarely a concern for side-effect-only hooks.
- **Data coupling via dict**: Hook data is passed as an untyped `dict`; callers and handlers must agree on key names by convention rather than by type.

## Extends
- ADR-006 (`006-asyncio-parallelism.md`) — async-first model; `emit_void` uses `asyncio.gather`
- ADR-007 (`007-hybrid-architecture.md`) — clean separation between config (frontmatter) and runtime behaviour (hook registry)

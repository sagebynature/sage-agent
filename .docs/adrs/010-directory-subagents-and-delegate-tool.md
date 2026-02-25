# ADR-010: Directory-Based Subagent References and Auto-Registered Delegate Tool

## Status
Accepted

## Context
Two gaps in the orchestration model needed to be addressed:

1. **Verbose subagent references**: Referencing subagents stored as directories (each with their own `AGENTS.md`) required `- config: research_agent` syntax, even though the config field added no clarity when pointing at a sibling directory. Users expected `- research_agent` to just work.

2. **Orchestrator agents could not delegate**: An agent with `subagents` had no tools to actually invoke them during its `run()` loop. The `Orchestrator.run_parallel()` helper worked from Python code or CLI (`sage agent orchestrate`), but the orchestrator *agent itself* was inert — it received a system prompt mentioning subagents it could never call.

## Decision

### Directory-based subagent references

Plain strings in the `subagents` YAML list are coerced to `{config: <string>}` via a Pydantic `field_validator` on `AgentConfig`. The existing `load_config()` function already resolves directories to `<dir>/AGENTS.md`, so no changes to the loader were needed.

```yaml
subagents:
  - research_agent            # directory → research_agent/AGENTS.md
  - config: helper.md         # explicit config reference (still works)
  - name: inline-helper       # inline definition (still works)
    model: gpt-4o-mini
```

### Auto-registered delegate tool

When an `Agent` is constructed with non-empty `subagents`, `__init__` calls `_register_delegation_tools()` which:

1. Creates an async `delegate(agent_name: str, task: str) -> str` closure wrapping `Agent.delegate()`
2. Builds a `ToolSchema` with an `enum` constraint listing available subagent names
3. Attaches the schema as `__tool_schema__` and registers the function in the agent's `ToolRegistry`

The LLM now sees `delegate` as a callable tool and can autonomously decide when and how to invoke subagents during its `run()` loop.

### Two orchestration paths

| Path | Command | Behavior |
|------|---------|----------|
| Agent delegation | `sage agent run` | Orchestrator agent uses the `delegate` tool during its run loop. The LLM decides sequencing and which subagents to call. |
| CLI parallel | `sage agent orchestrate` | CLI bypasses the orchestrator agent entirely. Runs all subagents in parallel with the same input via `Orchestrator.run_parallel()`. |

Both paths coexist. `sage agent run` is preferred when the orchestrator needs reasoning about *how* to decompose work. `sage agent orchestrate` is preferred for simple fan-out where every subagent gets the same task.

## Consequences

**Positive:**
- **Less boilerplate**: `- research_agent` replaces `- config: research_agent` for directory subagents
- **Autonomous orchestration**: Orchestrator agents can now actually use their subagents without external coordination
- **Backward compatible**: Existing `config:` and inline syntax continues to work unchanged
- **Discoverable**: The `delegate` tool schema includes an `enum` of subagent names and their descriptions, so the LLM knows exactly what's available

**Negative:**
- **Implicit tool registration**: The `delegate` tool appears automatically when subagents are present, which may surprise users who inspect an agent's tool list
- **No parallel delegation**: The `delegate` tool invokes one subagent at a time. Parallel fan-out still requires `Orchestrator.run_parallel()` or `sage agent orchestrate`
- **String ambiguity**: A plain string like `research_agent` is always treated as a config/directory reference, never as an inline name — this is consistent but could confuse users who expect inline shorthand

## Extends
- ADR-009 (`009-markdown-agent-definitions.md`) — subagent syntax within Markdown agent definitions
- ADR-006 (`006-asyncio-parallelism.md`) — async execution model for delegation

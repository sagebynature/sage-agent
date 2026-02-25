# ADR-007: Hybrid Config-First + Code Architecture

## Status
Accepted

## Context
The SDK must serve two audiences: operators who want to define agents via configuration files without writing code, and developers who need full programmatic control over agent behavior, custom providers, and dynamic orchestration.

A config-only approach would limit advanced use cases. A code-only approach would raise the barrier to entry.

## Decision
Support both declarative Markdown configuration (with YAML frontmatter) and a full Python API:

- **Config-first path:** Define agents in Markdown with YAML frontmatter, run with the CLI (`sage agent run AGENTS.md`). No Python required.
- **Code-first path:** Import `Agent`, `@tool`, `Orchestrator`, etc. and compose programmatically.
- **Bridging:** `Agent.from_config("AGENTS.md")` loads config into Python objects for hybrid workflows.

```markdown
# Config-first (AGENTS.md)
---
name: assistant
model: gpt-4o
description: A helpful AI assistant
---

You are a helpful assistant.
```

```python
# Code-first
agent = Agent(name="assistant", model="gpt-4o", description="A helpful assistant", body="You are helpful.")
result = await agent.run("Hello")
```

## Consequences
**Positive:**
- Low barrier to entry for non-programmers (YAML + CLI)
- Full flexibility for developers (Python API)
- `from_config` bridges both worlds for hybrid workflows
- Config agents are reproducible and version-controllable
- Same runtime regardless of how the agent was defined

**Negative:**
- Two ways to define agents may confuse new users
- Documentation must cover both paths clearly
- Config features must be kept in sync with code API capabilities
- Testing surface area is larger (both paths need coverage)

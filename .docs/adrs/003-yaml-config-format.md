# ADR-003: YAML + Markdown Configuration Format
**Status: Superseded by [ADR-009](009-markdown-agent-definitions.md)**

## Status
Superseded by ADR-009

## Context
The SDK needs a declarative format for defining agents without writing Python code. The format must express agent name, model, persona, tools, subagents, memory settings, and MCP server connections. It should be readable by non-programmers and easily version-controlled.

Alternatives considered included TOML (limited nesting support), JSON (verbose, no comments), and pure Python (requires programming knowledge).

## Decision
Use YAML for structural configuration and separate `.md` files for persona content. The `persona` field in YAML can be either an inline string or a path to a markdown file (resolved relative to the config directory).

```yaml
name: assistant
model: gpt-4o
persona: persona.md    # References ./persona.md
tools:
  - myapp.tools
max_turns: 10
```

Configuration is validated at load time using Pydantic models (`AgentConfig`).

## Consequences
**Positive:**
- Clean separation between structure (YAML) and content (Markdown)
- YAML is widely understood and supports comments
- Markdown personas can be long-form without cluttering config
- Pydantic validation catches errors early with clear messages
- Git-friendly for version control and code review

**Negative:**
- Two files per agent when using external persona files
- YAML indentation sensitivity can cause subtle errors
- Persona file path resolution adds complexity to the config loader

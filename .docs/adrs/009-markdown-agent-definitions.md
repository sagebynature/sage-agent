# ADR-009: Markdown Agent Definitions with YAML Front Matter

## Status
Accepted

## Context
The current YAML + separate Markdown persona file format (`003-yaml-config-format.md`) requires maintaining two files per agent — a `.yaml` config and an optional `persona.md` file. This introduces several issues:

1. **File proliferation**: Agents with personas require two files, making it harder to track which persona belongs to which agent
2. **Field ambiguity**: The `persona` field can be either an inline string or a path, requiring runtime resolution logic
3. **System prompt redundancy**: The `system_prompt` field in YAML duplicates the persona content, creating confusion about which one is used
4. **Alignment with Claude Code**: Claude Code agent definitions use YAML Front Matter + Markdown body, a clearer single-file pattern

## Decision
Replace the YAML + separate Markdown format with **single Markdown files using YAML Front Matter**:

- **File format**: `AGENTS.md` with YAML Front Matter (structured config) + Markdown body (system prompt)
- **Frontmatter**: Holds all AgentConfig fields except the system prompt
- **Body**: The raw Markdown text becomes the complete system prompt sent to the LLM
- **Hard cutover**: Stop supporting `.yaml`/`.yml` files entirely — no backward compatibility, no migration utilities
- **Breaking changes**:
  - `persona` field renamed to `description` (display/discovery only, NOT sent to model)
  - `system_prompt` field removed entirely (body replaces it)
  - All example agents converted to single `.md` files

### Example Format
```markdown
---
name: assistant
model: gpt-4o
description: A helpful AI assistant
permission:
  - shell
  - file_read
max_turns: 10
memory:
  backend: sqlite
  path: memory.db
  embedding: text-embedding-3-large
---

You are a helpful AI assistant. You provide clear, concise, and accurate responses.

You can:
- Answer questions
- Write code
- Solve problems
```

## Consequences

**Positive:**
- **Single file per agent**: One `.md` file replaces the YAML + persona.md pair
- **Clearer mental model**: Config + system prompt in one file, no field ambiguity
- **Alignment with Claude Code**: Consistent with Claude Code agent format (YAML frontmatter + body)
- **Simplified loading**: No complex persona file resolution logic needed
- **Cleaner codebase**: Remove `resolve_persona()`, `_resolve_personas()`, and `system_prompt` field

**Negative:**
- **Breaking change**: All agent definitions must be migrated (hard cutover)
- **No automatic migration**: Users must manually convert existing `.yaml` configs to `.md` format
- **Steeper learning curve**: Requires understanding YAML Front Matter syntax (mitigated by clear examples)

## Supersedes
- ADR-003 (`003-yaml-config-format.md`) — the old YAML + Markdown format is no longer supported

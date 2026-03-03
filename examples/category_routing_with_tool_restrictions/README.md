# Phase 1 Foundation Examples

Demonstrates the three new features from Phase 1:

## 1. Per-Agent Tool Restrictions

Agents can now specify `allowed_tools` (allowlist) and `blocked_tools` (blocklist) in their frontmatter:

- `blocked_tools`: Tools that are hidden and cannot be executed
- `allowed_tools`: Only these tools are visible/executable (all others blocked)

See `AGENTS.md` for blocklist usage and `researcher.md` for allowlist usage.

## 2. Session Continuity

The `delegate` tool now accepts an optional `session_id` parameter. When provided, the subagent resumes from its previous conversation state. The response includes `[Session: <id>]` for tracking.

## 3. Category-Based Model Routing

Define categories in `config.toml` with model overrides. Use the `category` parameter in `delegate` to route to different models:

```toml
[categories.quick]
model = "gpt-4o-mini"

[categories.deep]
model = "anthropic/claude-sonnet-4-20250514"
```

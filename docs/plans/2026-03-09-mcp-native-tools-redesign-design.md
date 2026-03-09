# MCP And Native Tools Redesign

## Summary

This design expands Sage's native tool runtime in five areas:

1. Structured tool results instead of string-only dispatch results
2. Namespaced MCP tool registration with centralized server configuration
3. Persistent process tools for long-lived CLI sessions
4. Expanded memory tools beyond store/recall
5. Tool metadata for risk, statefulness, and approval behavior

The MCP configuration model is also simplified. MCP server definitions move to a single global catalog in `config.toml`. Agents no longer define MCP servers inline. They only opt into globally defined servers by name using `enabled_mcp_servers`.

## Goals

- Make stateful native tools possible without overloading plain text responses
- Prevent MCP tool name collisions and preserve server provenance
- Keep MCP configuration simple and auditable
- Add first-class native primitives for persistent processes and richer memory access
- Make approvals and UI behavior more capability-aware

## Non-Goals

- Building browser automation in this phase
- Adding remote agent-to-agent execution in this phase
- Replacing the existing permission system wholesale
- Designing a generic workflow engine or scheduler in this phase

## Current State

Sage currently exposes a narrow built-in tool surface centered on file, shell, web, memory, and git categories. Tool dispatch returns `str(result)` at the registry boundary, which is sufficient for text tools but constraining for stateful resources such as MCP provenance, process handles, and richer memory operations. MCP tools are registered by discovered schema name only, which creates collision risk and weak provenance.

Configuration is also more flexible than necessary. `mcp_servers` can currently appear in agent frontmatter and in TOML defaults and per-agent overrides. That flexibility makes startup and security harder to reason about once MCP becomes a more central native runtime surface.

## Decision 1: Centralized MCP Server Catalog

MCP server definitions will exist only in `config.toml` under a top-level catalog:

```toml
[mcp_servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp"]

[mcp_servers.seqthink]
transport = "stdio"
command = "uvx"
args = ["sequential-thinking-mcp"]
```

Agents will select from that catalog using `enabled_mcp_servers`:

```toml
[defaults]
enabled_mcp_servers = ["context7"]

[agents.safe_coder]
enabled_mcp_servers = ["context7", "seqthink"]
```

Agent frontmatter may also specify:

```yaml
enabled_mcp_servers: [context7, seqthink]
```

Agent-local `mcp_servers` definitions will be removed.

### Rationale

- One source of truth for transport, command, environment, and timeout
- Better credential hygiene and operational review
- Clearer startup semantics
- Simpler mental model for users
- Better alignment with namespaced MCP tool registration

## Decision 2: Namespaced MCP Tool Registration

Discovered MCP tools will be registered under a runtime-visible namespaced name derived from server identity:

- `mcp_context7_resolve-library-id`
- `mcp_seqthink_next_step`

Internally, the registry will preserve:

- server name
- original upstream tool name
- discovered schema
- MCP client binding

The registry should execute namespaced tools by looking up this metadata rather than by raw schema name.

### Rationale

- Eliminates tool collisions across servers
- Makes tool provenance explicit to the LLM, telemetry, and UI
- Supports future per-server approval and observability policies

## Decision 3: Structured Tool Results

The runtime will introduce a typed result envelope instead of forcing all tool executions into plain strings.

Initial shape:

```python
class ToolResult(BaseModel):
    text: str | None = None
    json: dict[str, Any] | list[Any] | None = None
    artifacts: list[ToolArtifact] = Field(default_factory=list)
    resource: ToolResourceRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

The model-facing layer may still render a textual summary, but the runtime and UI should retain the structured payload.

### Required behavior

- Existing text tools continue to work with minimal changes
- The registry accepts either raw strings or `ToolResult`
- Telemetry and TUI can inspect structured payloads
- Resource references support later stateful tools such as persistent processes

### Rationale

This is the enabling substrate for the rest of the redesign. Without structured results, every stateful tool becomes an ad hoc string protocol.

## Decision 4: Persistent Process Tools

Add a first-class native process manager with these tools:

- `process_start(command, cwd=None, env=None, shell=False)`
- `process_send(process_id, input)`
- `process_read(process_id, max_chars=4000, since_cursor=None)`
- `process_wait(process_id, timeout=None)`
- `process_kill(process_id)`
- `process_list()`

### Runtime model

- Processes are started under a managed in-memory registry
- Each process gets a stable `process_id`
- Output is buffered with bounded retention and cursors
- The process manager integrates with existing sandbox policy where applicable
- Process lifetime is scoped to the current agent runtime/session unless later persisted deliberately

### Rationale

This fills the gap between one-shot shell execution and full background subagents. It enables REPLs, long-running dev servers, interactive CLIs, and iterative test/debug loops.

## Decision 5: Expanded Memory Tools

The memory subsystem will expose a richer native tool family:

- `memory_add(content, metadata=None)`
- `memory_search(query, limit=5)`
- `memory_get(memory_id)`
- `memory_list(limit=50, offset=0)`
- `memory_delete(memory_id)`
- `memory_stats()`

Optional later additions:

- `memory_update(memory_id, content=None, metadata=None)`
- `memory_link(source_id, target_id, relation)`

### Runtime model

- These tools wrap the existing memory backend instead of bypassing it
- `memory_search` returns ranked results and metadata
- `memory_stats` exposes counts and backend status
- IDs become stable references the model can use across turns

### Rationale

Current `memory_store` and `memory_recall` are too thin for an agent runtime that needs inspectable, manageable working memory.

## Decision 6: Tool Metadata

Every tool schema should gain optional runtime metadata describing:

- `risk_level`: `low | medium | high`
- `stateful`: boolean
- `resource_kind`: `process | memory | mcp | git | none`
- `approval_hint`: optional string
- `idempotent`: boolean
- `visible_name`: user-facing label if different from runtime name

This metadata is not a replacement for permissions. It is supplemental information for:

- approval UX
- telemetry
- TUI rendering
- future policy routing

### Rationale

As the tool surface grows, category-only permissions become too coarse for good UX and observability.

## Config Merge Semantics

The new MCP model should follow these rules:

- `config.toml` owns all `[mcp_servers.<name>]` definitions
- `enabled_mcp_servers` is selectable from `defaults`, `[agents.<name>]`, and frontmatter
- the effective list is top-level replacement, not deep merge
- unknown names fail validation during config load

This is intentionally simpler than the current `mcp_servers` behavior.

## Architecture Changes

### Config

- Add top-level `mcp_servers` to main config as the canonical catalog
- Add `enabled_mcp_servers` to defaults, per-agent overrides, and `AgentConfig`
- Remove `mcp_servers` from `AgentConfig`

### Registry

- Introduce a structured MCP registration record
- Register namespaced MCP tool schemas
- Preserve original upstream schema name and server provenance
- Allow execution to return structured results

### Agent Initialization

- Resolve `enabled_mcp_servers` against the global catalog
- Initialize only selected MCP clients
- Surface clear startup errors for unknown or failed servers

### Memory

- Extend the memory protocol surface as needed to support list/get/delete/stats
- Provide tool wrappers in `sage.tools.agent_tools.memory` or a dedicated memory tool module

### Processes

- Add a process manager module responsible for lifecycle, buffering, cleanup, and IDs
- Register process tools as built-ins behind a new permission category or an expanded shell/task model

### Telemetry And UI

- Record tool provenance and structured result metadata
- Show MCP server identity in tool displays
- Show process IDs and state where applicable

## Error Handling

- Unknown `enabled_mcp_servers` entries fail config validation
- Failed MCP initialization should identify the server by configured name
- Namespaced tool execution errors should mention both namespaced and upstream tool names
- Process reads on unknown or exited processes should return structured status, not ambiguous text
- Memory operations on unknown IDs should return explicit not-found errors

## Testing Strategy

- Config validation tests for global MCP catalog and `enabled_mcp_servers`
- Merge tests for defaults, per-agent overrides, and frontmatter replacement semantics
- Registry tests for MCP namespacing and collision prevention
- Backward-compatibility tests for existing string-returning tools
- Process manager tests for start/send/read/wait/kill and cleanup
- Memory tool tests for add/search/get/list/delete/stats
- Telemetry tests for structured results and MCP provenance

## Migration

### Breaking changes

- Agent frontmatter `mcp_servers` is removed
- Existing MCP tool names exposed to models will change to namespaced names

### Migration path

1. Define all MCP servers in `config.toml`
2. Replace per-agent `mcp_servers` blocks with `enabled_mcp_servers`
3. Update prompts/examples/tests to reference namespaced MCP tools if needed

## Rollout Order

1. Structured tool results
2. Centralized MCP config plus `enabled_mcp_servers`
3. Namespaced MCP registration
4. Tool metadata
5. Expanded memory tools
6. Persistent process tools

This order minimizes rework because MCP, memory, and processes all benefit from the structured-result substrate.

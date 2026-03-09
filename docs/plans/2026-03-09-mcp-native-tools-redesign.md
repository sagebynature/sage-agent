# MCP And Native Tools Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce structured tool results, centralized MCP configuration with per-agent selection, namespaced MCP tools, expanded memory tools, persistent process tools, and tool metadata without breaking the current text-first runtime in one pass.

**Architecture:** Keep the current `ToolRegistry.execute()` string contract as a compatibility wrapper while adding a structured result path underneath it. Move MCP connection details into the main TOML config, let agents opt into named servers through `enabled_mcp_servers`, and make the registry store server-aware MCP bindings. Layer in richer memory and process tools only after the result and metadata substrate exists.

**Tech Stack:** Python 3.10+, Pydantic, asyncio, aiosqlite, pytest

---

### Task 1: Simplify MCP Configuration

**Files:**
- Modify: `sage/config.py`
- Modify: `sage/main_config.py`
- Modify: `sage/agent.py`
- Modify: `tests/test_config.py`
- Modify: `tests/test_main_config.py`
- Modify: `tests/test_agent.py`

**Step 1: Write the failing config tests**

Add tests that assert:

- `MainConfig` accepts top-level `mcp_servers`
- `ConfigOverrides` and `AgentOverrides` accept `enabled_mcp_servers`
- `AgentConfig` accepts `enabled_mcp_servers`
- frontmatter `mcp_servers` is rejected
- `Agent.from_config()` builds only the selected MCP clients

Example test sketch:

```python
def test_agent_config_enabled_mcp_servers_field(tmp_path: Path) -> None:
    cfg_path = _write_md(
        tmp_path / "AGENTS.md",
        {"name": "agent", "model": "gpt-4o", "enabled_mcp_servers": ["filesystem"]},
    )
    config = load_config(cfg_path)
    assert config.enabled_mcp_servers == ["filesystem"]
```

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest tests/test_config.py tests/test_main_config.py tests/test_agent.py -k "mcp or enabled_mcp_servers" -v
```

Expected: failures referencing missing `enabled_mcp_servers` support or old frontmatter MCP behavior.

**Step 3: Implement the config migration**

Make these exact changes:

- In `sage/config.py`, remove `mcp_servers` from `AgentConfig`
- In `sage/config.py`, add `enabled_mcp_servers: list[str] | None = None` to `AgentConfig`
- In `sage/main_config.py`, remove `mcp_servers` from `ConfigOverrides`
- In `sage/main_config.py`, add `enabled_mcp_servers: list[str] | None = None` to `ConfigOverrides`
- In `sage/main_config.py`, add `mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)` to `MainConfig`
- In `sage/agent.py`, change `_build_mcp_clients()` to resolve names from `config.mcp_servers`

Implementation sketch for `sage/agent.py`:

```python
def _build_mcp_clients(config: AgentConfig, agent_config: AgentConfig) -> list[MCPClient]:
    selected = agent_config.enabled_mcp_servers or []
    clients: list[MCPClient] = []
    for server_name in selected:
        mcp_cfg = config._mcp_server_catalog[server_name]
        clients.append(MCPClient(server_name=server_name, ...))
    return clients
```

**Step 4: Add validation for unknown MCP server names**

In config loading, fail fast if any `enabled_mcp_servers` entry is not defined in `MainConfig.mcp_servers`.

Example validation behavior:

```python
missing = sorted(set(enabled) - set(central.mcp_servers))
if missing:
    raise ConfigError(f"Unknown MCP server(s): {', '.join(missing)}")
```

**Step 5: Re-run the tests**

Run:

```bash
pytest tests/test_config.py tests/test_main_config.py tests/test_agent.py -k "mcp or enabled_mcp_servers" -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add sage/config.py sage/main_config.py sage/agent.py tests/test_config.py tests/test_main_config.py tests/test_agent.py
git commit -m "refactor: centralize MCP server configuration"
```

---

### Task 2: Add Structured Tool Results And Tool Metadata

**Files:**
- Modify: `sage/models.py`
- Modify: `sage/tools/registry.py`
- Modify: `sage/tools/decorator.py`
- Modify: `tests/test_tools/test_registry.py`
- Modify: `tests/test_tools/test_decorator.py`

**Step 1: Write the failing model and registry tests**

Add tests that assert:

- `ToolSchema` can carry metadata
- `ToolRegistry` can normalize raw strings into structured results
- `ToolRegistry.execute()` still returns plain text for legacy callers
- `ToolRegistry.execute_result()` returns a `ToolResult`

Example test sketch:

```python
async def test_execute_result_wraps_plain_string() -> None:
    registry = ToolRegistry()
    registry.register(add)
    result = await registry.execute_result("add", {"a": 1, "b": 2})
    assert result.text == "3"
    assert result.json is None
```

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest tests/test_tools/test_registry.py tests/test_tools/test_decorator.py -k "execute_result or metadata" -v
```

Expected: failures because `ToolResult`, metadata, and `execute_result()` do not exist yet.

**Step 3: Add the new models**

In `sage/models.py`, add:

```python
class ToolMetadata(BaseModel):
    risk_level: Literal["low", "medium", "high"] = "low"
    stateful: bool = False
    resource_kind: Literal["none", "mcp", "memory", "process", "git"] = "none"
    approval_hint: str | None = None
    idempotent: bool = True
    visible_name: str | None = None


class ToolResourceRef(BaseModel):
    kind: str
    resource_id: str


class ToolResult(BaseModel):
    text: str | None = None
    json: dict[str, Any] | list[Any] | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    resource: ToolResourceRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def render_text(self) -> str:
        return self.text or ""
```

Extend `ToolSchema`:

```python
class ToolSchema(BaseModel):
    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    metadata: ToolMetadata | None = None
```

**Step 4: Add compatibility normalization in the registry**

In `sage/tools/registry.py`:

- add `_normalize_tool_result()`
- add `execute_result() -> ToolResult`
- keep `execute()` as:

```python
async def execute(self, name: str, arguments: dict[str, Any]) -> str:
    result = await self.execute_result(name, arguments)
    return result.render_text()
```

**Step 5: Re-run the tests**

Run:

```bash
pytest tests/test_tools/test_registry.py tests/test_tools/test_decorator.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add sage/models.py sage/tools/registry.py sage/tools/decorator.py tests/test_tools/test_registry.py tests/test_tools/test_decorator.py
git commit -m "feat: add structured tool results and metadata"
```

---

### Task 3: Namespace MCP Tools And Preserve Provenance

**Files:**
- Modify: `sage/mcp/client.py`
- Modify: `sage/tools/registry.py`
- Modify: `sage/agent.py`
- Modify: `tests/test_tools/test_registry.py`
- Modify: `tests/test_agent.py`
- Modify: `tests/test_mcp/test_client.py`

**Step 1: Write the failing MCP namespacing tests**

Add tests that assert:

- MCP tools are registered as `mcp_<server>_<tool>`
- collisions across two MCP servers do not overwrite one another
- execution routes to the correct client and upstream tool name

Example test sketch:

```python
async def test_register_mcp_tool_namespaces_by_server() -> None:
    registry = ToolRegistry()
    schema = ToolSchema(name="search", description="Search", parameters={})
    client = AsyncMock()
    registry.register_mcp_tool("context7", schema, client)
    schemas = registry.get_schemas()
    assert any(s.name == "mcp_context7_search" for s in schemas)
```

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest tests/test_tools/test_registry.py tests/test_agent.py tests/test_mcp/test_client.py -k "mcp and namespace" -v
```

Expected: failures because MCP registration is currently raw-name only.

**Step 3: Make the MCP client server-aware**

Extend `MCPClient.__init__()` to accept and store `server_name`.

Example:

```python
def __init__(self, *, server_name: str | None = None, transport: str = "stdio", ...):
    self._server_name = server_name
```

**Step 4: Replace raw-name MCP registration**

In `sage/tools/registry.py`, add a structured binding:

```python
@dataclass(slots=True)
class MCPToolBinding:
    server_name: str
    upstream_name: str
    client: MCPClient
    schema: ToolSchema
```

Register namespaced tools:

```python
runtime_name = f"mcp_{server_name}_{schema.name}"
```

Route execution with:

```python
binding = self._mcp_tools[name]
return await binding.client.call_tool(binding.upstream_name, arguments)
```

**Step 5: Re-run the tests**

Run:

```bash
pytest tests/test_tools/test_registry.py tests/test_agent.py tests/test_mcp/test_client.py -k "mcp" -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add sage/mcp/client.py sage/tools/registry.py sage/agent.py tests/test_tools/test_registry.py tests/test_agent.py tests/test_mcp/test_client.py
git commit -m "feat: namespace MCP tools by server"
```

---

### Task 4: Expand The Memory Tool Family

**Files:**
- Modify: `sage/tools/agent_tools/memory.py`
- Modify: `tests/test_memory/test_memory_forget_tool.py`
- Create: `tests/test_memory/test_memory_tool_suite.py`

**Step 1: Write the failing memory tool tests**

Add tests that assert:

- `memory_add` stores content and returns a memory ID
- `memory_search` returns ranked entries
- `memory_get` returns a single entry
- `memory_list` paginates
- `memory_delete` removes a record
- `memory_stats` returns count and backend status

Example test sketch:

```python
async def test_memory_add_returns_id(tmp_path: Path) -> None:
    agent = _make_agent_with_memory(tmp_path)
    result = await agent.tool_registry.execute_result(
        "memory_add",
        {"content": "release note", "metadata": {"kind": "note"}},
    )
    assert result.resource is not None
    assert result.resource.resource_id
```

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest tests/test_memory/test_memory_forget_tool.py tests/test_memory/test_memory_tool_suite.py -v
```

Expected: failures because only `memory_store`, `memory_recall`, and `memory_forget` exist today.

**Step 3: Implement the new tool set**

In `sage/tools/agent_tools/memory.py`, keep legacy tools for compatibility and add:

```python
@_tool
async def memory_add(content: str, metadata: dict[str, str] | None = None) -> ToolResult:
    memory_id = await memory_ref.store(content, metadata or {})
    return ToolResult(
        text=f"Stored memory {memory_id}",
        resource=ToolResourceRef(kind="memory", resource_id=memory_id),
        metadata={"memory_id": memory_id},
    )
```

Implement `memory_search`, `memory_get`, `memory_list`, `memory_delete`, and `memory_stats` on top of the existing `MemoryProtocol` methods.

**Step 4: Register metadata for memory tools**

Set `ToolSchema.metadata` on the richer memory tools:

```python
memory_add.__tool_schema__.metadata = ToolMetadata(
    risk_level="low",
    stateful=True,
    resource_kind="memory",
    idempotent=False,
)
```

**Step 5: Re-run the tests**

Run:

```bash
pytest tests/test_memory/test_memory_forget_tool.py tests/test_memory/test_memory_tool_suite.py tests/test_memory/test_enriched_protocol.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add sage/tools/agent_tools/memory.py tests/test_memory/test_memory_forget_tool.py tests/test_memory/test_memory_tool_suite.py
git commit -m "feat: expand native memory tools"
```

---

### Task 5: Add Persistent Process Tools

**Files:**
- Create: `sage/tools/process_manager.py`
- Create: `sage/tools/process_tools.py`
- Modify: `sage/config.py`
- Modify: `sage/tools/registry.py`
- Modify: `sage/permissions/policy.py`
- Modify: `sage/agent.py`
- Create: `tests/test_tools/test_process_tools.py`
- Modify: `tests/test_permissions/test_policy.py`

**Step 1: Write the failing process tool tests**

Add tests that assert:

- `process_start` returns a process resource ID
- `process_send` writes to stdin
- `process_read` returns buffered output
- `process_wait` returns exit status
- `process_kill` terminates a running process
- permissions can gate process tools independently

Example test sketch:

```python
async def test_process_start_and_wait(tmp_path: Path) -> None:
    manager = ProcessManager()
    result = await process_start(command=["python", "-c", "print('hi')"])
    proc_id = result.resource.resource_id
    waited = await process_wait(proc_id, timeout=1.0)
    assert waited.json["returncode"] == 0
```

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest tests/test_tools/test_process_tools.py tests/test_permissions/test_policy.py -k "process" -v
```

Expected: failures because process tools and the `process` permission category do not exist.

**Step 3: Implement the process manager**

In `sage/tools/process_manager.py`, create a bounded async process registry:

```python
class ProcessManager:
    async def start(self, command: list[str] | str, *, cwd: str | None = None, env: dict[str, str] | None = None, shell: bool = False) -> ProcessHandle: ...
    async def send(self, process_id: str, data: str) -> None: ...
    async def read(self, process_id: str, *, max_chars: int = 4000, since_cursor: int | None = None) -> ToolResult: ...
    async def wait(self, process_id: str, timeout: float | None = None) -> ToolResult: ...
    async def kill(self, process_id: str) -> ToolResult: ...
```

Use `asyncio.create_subprocess_exec()` for argv mode and `create_subprocess_shell()` only when `shell=True`.

**Step 4: Register the tools and permission category**

Make these exact changes:

- add `process: PermissionValue | None = None` in `sage/config.py`
- add `"process"` to `CATEGORY_TOOLS` and `CATEGORY_ARG_MAP` in `sage/tools/registry.py`
- register process tools during agent setup
- teach `sage/permissions/policy.py` about the new category through the existing maps

Attach metadata like:

```python
ToolMetadata(
    risk_level="medium",
    stateful=True,
    resource_kind="process",
    idempotent=False,
)
```

**Step 5: Re-run the tests**

Run:

```bash
pytest tests/test_tools/test_process_tools.py tests/test_permissions/test_policy.py -k "process" -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add sage/tools/process_manager.py sage/tools/process_tools.py sage/config.py sage/tools/registry.py sage/permissions/policy.py sage/agent.py tests/test_tools/test_process_tools.py tests/test_permissions/test_policy.py
git commit -m "feat: add persistent process tools"
```

---

### Task 6: Backfill Metadata On Existing Native Tools

**Files:**
- Modify: `sage/tools/builtins.py`
- Modify: `sage/tools/web_tools.py`
- Modify: `sage/tools/agent_tools/memory.py`
- Modify: `sage/tools/agent_tools/background.py`
- Modify: `sage/tools/agent_tools/planning.py`
- Modify: `tests/test_tools/test_builtins.py`
- Modify: `tests/test_tools/test_registry.py`

**Step 1: Write the failing metadata tests**

Add tests that assert selected tools expose metadata:

- `shell` is high risk
- `http_request` and `web_fetch` are medium risk
- memory/process tools are stateful
- planning tools are low risk

Example test sketch:

```python
def test_shell_schema_metadata() -> None:
    assert shell.__tool_schema__.metadata.risk_level == "high"
    assert shell.__tool_schema__.metadata.idempotent is False
```

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest tests/test_tools/test_builtins.py tests/test_tools/test_registry.py -k "metadata" -v
```

Expected: failures because existing tool schemas do not yet carry metadata.

**Step 3: Annotate the schemas**

After each tool definition or manual schema creation, attach metadata explicitly.

Example:

```python
shell.__tool_schema__.metadata = ToolMetadata(
    risk_level="high",
    stateful=False,
    resource_kind="none",
    approval_hint="Executes a shell command",
    idempotent=False,
)
```

**Step 4: Keep descriptions and metadata aligned**

Review manual schemas in planning/background/delegation modules and make sure `visible_name` and `approval_hint` are meaningful where needed.

**Step 5: Re-run the tests**

Run:

```bash
pytest tests/test_tools/test_builtins.py tests/test_tools/test_registry.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add sage/tools/builtins.py sage/tools/web_tools.py sage/tools/agent_tools/memory.py sage/tools/agent_tools/background.py sage/tools/agent_tools/planning.py tests/test_tools/test_builtins.py tests/test_tools/test_registry.py
git commit -m "feat: add metadata to native tools"
```

---

### Task 7: Update Docs And Examples For The New MCP Model

**Files:**
- Modify: `README.md`
- Modify: `examples/mcp-assistant.md`
- Modify: `examples/orchestrated_agents/config.toml`
- Modify: `examples/safe_coder/config.toml`
- Modify: `tests/test_cli/test_main.py`
- Modify: `tests/test_integration_examples.py`

**Step 1: Write the failing docs/example tests**

Add or update tests to assert:

- examples use `[mcp_servers.<name>]` in TOML
- agents use `enabled_mcp_servers`
- CLI config summaries still report configured MCP servers correctly

Example test sketch:

```python
def test_mcp_assistant_uses_enabled_mcp_servers() -> None:
    content = Path("examples/mcp-assistant.md").read_text()
    assert "enabled_mcp_servers:" in content
    assert "mcp_servers:" not in content
```

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest tests/test_cli/test_main.py tests/test_integration_examples.py -k "mcp" -v
```

Expected: failures because docs and examples still reference the old MCP layout.

**Step 3: Update the examples and README**

Document:

- global catalog under `config.toml`
- per-agent selection via `enabled_mcp_servers`
- namespaced MCP tools such as `mcp_context7_*`

Update the example snippets to match the new config model exactly.

**Step 4: Verify manually**

Run:

```bash
rg -n "mcp_servers:|enabled_mcp_servers|\\[mcp_servers\\." README.md examples tests -S
```

Expected:

- no agent frontmatter `mcp_servers:` examples remain
- `enabled_mcp_servers` appears in updated agent examples
- `[mcp_servers.<name>]` appears in TOML examples

**Step 5: Re-run the tests**

Run:

```bash
pytest tests/test_cli/test_main.py tests/test_integration_examples.py -k "mcp" -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add README.md examples/mcp-assistant.md examples/orchestrated_agents/config.toml examples/safe_coder/config.toml tests/test_cli/test_main.py tests/test_integration_examples.py
git commit -m "docs: update MCP configuration examples"
```


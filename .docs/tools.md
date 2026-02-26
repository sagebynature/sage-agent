# Sage Tools

Sage tools are functions that agents can call during execution. The LLM sees
tool schemas (name, description, parameters) and decides when to invoke them.
Results are fed back into the conversation for the next turn.

This document covers the built-in tools, the tool registry, permissions,
MCP integration, and how to create your own tools.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Built-in Tools](#built-in-tools)
  - [Shell](#shell)
  - [Shell Sandbox](#shell-sandbox)
  - [File Read](#file-read)
  - [File Write](#file-write)
  - [File Edit](#file-edit)
  - [Web Tools](#web-tools)
  - [Memory Tools](#memory-tools)
- [Configuring Tools](#configuring-tools)
  - [In Agent Frontmatter](#in-agent-frontmatter)
  - [In config.toml](#in-configtoml)
  - [Tool Name Resolution](#tool-name-resolution)
- [Permissions](#permissions)
  - [Permission Actions](#permission-actions)
  - [Category-Based Rules](#category-based-rules)
  - [Pattern Matching](#pattern-matching)
  - [Examples](#permission-examples)
- [Extensions](#extensions)
  - [Loading Custom Tool Modules](#loading-custom-tool-modules)
- [MCP Integration](#mcp-integration)
- [Creating Custom Tools](#creating-custom-tools)
  - [The @tool Decorator](#the-tool-decorator)
  - [Supported Types](#supported-types)
  - [Stateful Tools with ToolBase](#stateful-tools-with-toolbase)
  - [Registering Custom Tools](#registering-custom-tools)
- [Security](#security)
- [Architecture](#architecture)

---

## Quick Start

Give an agent the built-in shell and file tools:

```yaml
# AGENTS.md
---
name: my-agent
model: azure_ai/gpt-4o
permission:
  read: allow
  edit: allow
  shell: allow
---

You are a helpful coding assistant.
```

Or allow all built-in tools via a broad permission:

```yaml
permission:
  read: allow
  edit: allow
  shell: allow
  web: allow
  memory: allow
```

Run it:

```bash
sage agent run . -i "What files are in this project?"
```

---

## Built-in Tools

### Shell

**Name:** `shell`
**Module:** `sage.tools.builtins`

Runs a shell command and returns combined stdout and stderr.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `command` | `str` | yes | Shell command to execute |

**Returns:** Command output. Stderr is included under a `[stderr]` header.

**Security:** A regex blocklist prevents destructive commands. See
[Security](#security) for the full list. For stronger process isolation, enable
the optional [Shell Sandbox](#shell-sandbox).

```
Agent calls: shell(command="ls -la src/")
→ "total 24\ndrwxr-xr-x 3 user user 4096 ..."
```

---

### Shell Sandbox

For stricter isolation, Sage can run shell commands inside a **sandbox** in
addition to the blocklist. Enable it via the `sandbox:` field in `AGENTS.md`
frontmatter:

```yaml
sandbox:
  backend: native       # "native" (default) or "bubblewrap"
  allowed_env:          # extra env vars to pass through
    - MY_TOKEN
  network: true         # allow network access (bubblewrap backend only)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `backend` | `"native"` or `"bubblewrap"` | `"native"` | Sandbox implementation |
| `allowed_env` | `list[str]` | `[]` | Extra environment variables to pass through |
| `network` | `bool` | `true` | Allow network (bubblewrap only) |

**Native sandbox** strips the child process environment to a trusted minimum
(`PATH`, `HOME`, `USER`, `LANG`, `TERM`) plus any variables explicitly listed in
`allowed_env`. This blocks common bypass vectors such as `$SHELL` and injected
`$BASH_FUNC_*` variables.

**Bubblewrap sandbox** provides Linux kernel namespace isolation via the `bwrap`
binary (must be installed separately). It mounts only safe read-only filesystem
views and can disable network access (`network: false`).

When `sandbox:` is not set, commands run in the current process environment with
only the blocklist as protection.

---

### File Read

**Name:** `file_read`
**Module:** `sage.tools.builtins`

Reads and returns the contents of a file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | `str` | yes | Path to the file (relative to working directory) |

**Returns:** UTF-8 file contents.

**Security:** Path is validated to be within the current working directory.

---

### File Write

**Name:** `file_write`
**Module:** `sage.tools.builtins`

Writes content to a file, creating parent directories as needed.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | `str` | yes | Destination path (relative to working directory) |
| `content` | `str` | yes | Content to write |

**Returns:** Confirmation message with byte count written.

**Security:** Path is validated to be within the current working directory.

---

### File Edit

**Name:** `file_edit`
**Module:** `sage.tools.file_tools`

Replaces exact string occurrences in a file. This is the preferred way for
agents to make targeted code changes — read first, then replace the exact
substring.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | `str` | yes | | File to edit |
| `old_string` | `str` | yes | | Exact string to find |
| `new_string` | `str` | yes | | Replacement string |
| `replace_all` | `bool` | no | `false` | Replace all occurrences instead of just the first |

**Returns:** Confirmation message with replacement count.

**Behavior:**
- Fails if `old_string` is not found in the file.
- Fails if `old_string` matches multiple locations and `replace_all` is `false`.
- Uses atomic write (temp file + rename) to prevent corruption.
- Preserves original file permissions.

---

### Web Tools

Both web tools live in `sage.tools.web_tools`.

#### web_fetch

Fetches a URL and returns the content as markdown.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | `str` | yes | URL to fetch |

**Returns:** Page content converted to markdown via
[markdownify](https://github.com/matthewwithanm/python-markdownify),
truncated to 10,000 characters.

**Security:** Full SSRF protection with DNS rebinding (TOCTOU) prevention: the
hostname is resolved exactly once, the resulting IP is validated, and that pinned
IP is used for the actual connection. Only `http`/`https` schemes allowed. See
[URL Validation](#url-validation-ssrf-protection) for details.

#### web_search

Searches the web using DuckDuckGo.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | `str` | yes | | Search query |
| `max_results` | `int` | no | `5` | Number of results |

**Returns:** Numbered list of results with title, URL, and snippet.

---

### Memory Tools

Both memory tools live in `sage.tools.builtins`. They provide simple
key-value persistence across sessions.

#### memory_store

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | `str` | yes | Key to store under |
| `value` | `str` | yes | Value to store |

Data is persisted as JSON at `~/.sage/memory_store.json` (override with
`SAGE_MEMORY_PATH` environment variable).

#### memory_recall

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | `str` | yes | Search string |

Performs case-insensitive substring matching on both keys and values.
Returns a JSON object of matches.

> **Note:** These are the simple built-in memory tools. For vector-based
> semantic memory (embedding + SQLite), configure the `memory:` section
> in your agent frontmatter instead. See the
> [memory_agent example](../examples/memory_agent/).

---

## Configuring Tools

### In Agent Frontmatter

The `permission:` and `extensions:` fields in your `AGENTS.md` frontmatter
control which tools the agent has access to.

**Permission format** grants access to built-in tools by category:

```yaml
---
name: my-agent
model: azure_ai/gpt-4o
permission:
  read: allow      # registers file_read
  edit: allow      # registers file_write, file_edit
  shell: allow     # registers shell
  web: allow       # registers web_fetch, web_search, http_request
  memory: allow    # registers memory_store, memory_recall
---
```

Permission values can be `"allow"`, `"deny"`, `"ask"`, or a dict of patterns
(see [Permissions](#permissions) below).

**Extensions format** loads custom tools from Python modules:

```yaml
extensions:
  - myapp.tools           # loads all @tool functions in myapp.tools
  - myapp.tools:my_tool   # loads only my_tool from myapp.tools
```

### In config.toml

Set default permissions and extensions for all agents in the `[defaults]`
section of `config.toml`. Individual agents can override this in their
frontmatter or in `[agents.<name>]` sections.

```toml
[defaults]
permission.read = "allow"
permission.edit = "allow"
permission.shell = "ask"

[agents.researcher]
permission.web = "allow"
extensions = ["myapp.tools"]
```

The override is a full replacement — not a merge. If an agent specifies
`permission:` in its frontmatter, the default is replaced entirely.

### Tool Name Resolution

When you reference a tool name (in `extensions:` or via the registry),
it is resolved in this order:

| Format | Example | Resolution |
|--------|---------|------------|
| Built-in name | `shell` | Registered when `permission.shell: allow` |
| Built-in name | `file_read` | Registered when `permission.read: allow` |
| Dotted module path | `myapp.tools` | Imports module → registers all `@tool` functions found |
| Module with selector | `myapp.tools:search` | Imports module → registers only `search` |

**Built-in tools** (auto-registered by category):

| Category | Tools |
|----------|-------|
| `read` | `file_read` |
| `edit` | `file_write`, `file_edit` |
| `shell` | `shell` |
| `web` | `web_fetch`, `web_search`, `http_request` |
| `memory` | `memory_store`, `memory_recall` |

**Extended tool lookup** (non-builtin, auto-resolved to modules):

| Name | Module |
|------|--------|
| `file_edit` | `sage.tools.file_tools` |
| `web_search` | `sage.tools.web_tools` |
| `web_fetch` | `sage.tools.web_tools` |

---

## Permissions

Permissions control whether a tool call is allowed, denied, or requires user
approval. They are configured in the `permission:` section of an agent's
frontmatter or `config.toml`.

### Permission Actions

| Action | Behavior |
|--------|----------|
| `allow` | Tool call proceeds without prompting |
| `deny` | Tool call is blocked; agent receives an error |
| `ask` | User is prompted for approval (default) |

### Category-Based Rules

Permissions are organized by **category**, not individual tool names.
Each category groups related tools:

```yaml
permission:
  read: allow      # allow file_read
  edit: deny       # deny file_write, file_edit
  shell: ask       # ask for approval on shell commands
  web: allow       # allow web_fetch, web_search, http_request
  memory: deny     # deny memory_store, memory_recall
```

This grants category-level control. For fine-grained control over specific
commands or paths, use **patterns** (see below).

### Pattern Matching

For the `shell` category (or any tool with a `command` parameter), you can
define patterns for fine-grained control. Patterns use
[fnmatch](https://docs.python.org/3/library/fnmatch.html) glob syntax.
**Last match wins** — so define broad rules first and add specific overrides.

```yaml
permission:
  shell:
    "*": deny              # deny all commands by default
    "git log *": allow     # allow git log
    "git diff *": allow    # allow git diff
    "git status": allow    # allow git status
    "ls *": allow          # allow ls
```

For the `read` and `edit` categories, patterns match against file paths:

```yaml
permission:
  read:
    "*": allow             # allow all reads
    "*.env": deny          # except .env files
    ".secret/*": deny      # and files in .secret/
  edit:
    "*": ask               # ask for approval on edits
    "test_*.py": allow     # auto-allow test file edits
    "src/**": ask          # edits to src/ require approval
```

For `web`, patterns match against URLs:

```yaml
permission:
  web:
    "*": deny                      # deny web by default
    "https://api.github.com/*": allow   # allow GitHub API
```

### Permission Examples

**Read-only reviewer** — can read files and search but cannot modify anything:

```yaml
permission:
  read: allow
  edit: deny
  shell: deny
  web: allow
  memory: deny
```

**Supervised coder** — reads are free, edits need approval, shell is denied:

```yaml
permission:
  read: allow
  edit: ask
  shell: deny
  web: allow
  memory: deny
```

**Safe shell explorer** — allow git and safe inspection commands:

```yaml
permission:
  read: allow
  edit: deny
  shell:
    "*": deny
    "git status": allow
    "git log *": allow
    "git diff *": allow
    "ls *": allow
    "find *": allow
  web: allow
  memory: deny
```

See [`examples/permissions_agent/`](../examples/permissions_agent/) and
[`examples/safe_coder/`](../examples/safe_coder/) for full working examples.

---

## Extensions

### Loading Custom Tool Modules

The `extensions:` list in your agent frontmatter allows you to load custom
tools from Python modules.

```yaml
---
name: my-agent
model: azure_ai/gpt-4o
extensions:
  - myapp.tools
  - myapp.tools:specific_tool
---
```

The registry imports each module and registers every `@tool`-decorated
function and every `ToolBase` subclass it finds. You can specify a single
function using the `module:name` syntax.

---

## MCP Integration

[MCP (Model Context Protocol)](https://modelcontextprotocol.io/) servers
expose external tools over a standard transport. Sage connects to MCP servers,
discovers their tools, and registers them alongside native tools — the agent
sees a unified tool list.

### Configuring MCP Servers

Add `mcp_servers:` to your agent frontmatter:

```yaml
---
name: mcp-assistant
model: azure_ai/claude-sonnet-4-6
mcp_servers:
  - transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
permission:
  read: allow
  shell: allow
---
```

Or in `config.toml`:

```toml
[[defaults.mcp_servers]]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]

[[defaults.mcp_servers]]
transport = "sse"
url = "http://localhost:8080/sse"
```

### MCP Server Config Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `transport` | `"stdio"` or `"sse"` | `"stdio"` | Connection transport |
| `command` | `str` | `None` | Command to launch (stdio transport) |
| `url` | `str` | `None` | Server URL (sse transport) |
| `args` | `list[str]` | `[]` | Command-line arguments |
| `env` | `dict[str, str]` | `{}` | Environment variables |

### How It Works

1. On first agent `run()` or `stream()`, all MCP servers are connected.
2. `MCPClient.discover_tools()` retrieves `ToolSchema` objects from each server.
3. Schemas are registered in the agent's `ToolRegistry`.
4. The agent sees MCP tools alongside native tools.
5. When the LLM calls an MCP tool, the registry routes the call through
   `MCPClient.call_tool()`.

See [`examples/mcp_agent/`](../examples/mcp_agent/) for a working example.

---

## Creating Custom Tools

### The @tool Decorator

The `@tool` decorator converts any function into a tool. It inspects the
function's name, docstring, and type hints to generate a `ToolSchema`
automatically.

```python
from sage.tools import tool

@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    allowed = set("0123456789+-*/.(). ")
    if not all(c in allowed for c in expression):
        return "Error: expression contains invalid characters"
    try:
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"Error: {e}"

@tool
def word_count(text: str) -> str:
    """Count the words in a text."""
    count = len(text.split())
    return f"{count} words"
```

Rules:
- The function name becomes the tool name.
- The docstring becomes the tool description (shown to the LLM).
- All parameters must have type hints.
- Return type should be `str` (results are stringified regardless).
- Functions can be sync or async — the registry handles both.
- The decorator does not wrap the function; it attaches a `__tool_schema__`
  attribute and returns the function unchanged.

### Supported Types

The decorator maps Python types to JSON Schema:

| Python Type | JSON Schema Type |
|-------------|-----------------|
| `str` | `string` |
| `int` | `integer` |
| `float` | `number` |
| `bool` | `boolean` |
| `list` | `array` |
| `dict` | `object` |
| `list[str]` | `array` with `items: {type: string}` |
| `dict[str, int]` | `object` with `additionalProperties: {type: integer}` |
| `Optional[X]` | Type of `X` (parameter marked as not required) |
| Pydantic `BaseModel` | Inlined from `model_json_schema()` |

### Stateful Tools with ToolBase

For tools that need setup/teardown (database connections, file handles, etc.),
extend `ToolBase`:

```python
from sage.tools import ToolBase, tool

class DatabaseTool(ToolBase):
    def __init__(self, connection_string: str) -> None:
        super().__init__()
        self._conn_str = connection_string
        self._db = None

    async def setup(self) -> None:
        """Called before the tool is first used."""
        self._db = await connect(self._conn_str)

    async def teardown(self) -> None:
        """Called when the tool is no longer needed."""
        if self._db:
            await self._db.close()

    @tool
    async def query(self, sql: str) -> str:
        """Run a read-only SQL query."""
        rows = await self._db.fetch(sql)
        return str(rows)
```

`ToolBase` automatically collects all methods decorated with `@tool` via
`get_tools()`. When registered with a `ToolRegistry`, the instance's
lifecycle methods are managed.

### Registering Custom Tools

**Option 1: Module path in extensions** (recommended)

Put your tools in a Python module and reference it in the `extensions:` list:

```python
# myproject/tools.py
from sage.tools import tool

@tool
def my_tool(input: str) -> str:
    """Do something useful."""
    return f"Result: {input}"
```

```yaml
# AGENTS.md
---
name: my-agent
extensions:
  - myproject.tools
---
```

The registry imports the module and registers every `@tool`-decorated
function and every `ToolBase` subclass it finds.

To register a single function from a module:

```yaml
extensions:
  - myproject.tools:my_tool
```

**Option 2: Direct registration in code**

```python
from sage.agent import Agent
from sage.tools import tool

@tool
def greet(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"

agent = Agent(
    name="greeter",
    model="azure_ai/gpt-4o",
    tools=[greet],
)
```

**Option 3: ToolBase instance**

```python
db_tool = DatabaseTool("sqlite:///app.db")
agent = Agent(
    name="analyst",
    model="azure_ai/gpt-4o",
    tools=[db_tool],
)
```

See [`examples/custom_tools/`](../examples/custom_tools/) for a complete
working example.

---

## Security

### Shell Command Blocklist

The `shell` tool blocks commands matching these patterns:

| Category | Blocked Patterns |
|----------|-----------------|
| Destructive filesystem | `rm -rf /`, `mkfs`, `dd of=/dev/` |
| System control | `shutdown`, `reboot`, `systemctl halt\|poweroff\|reboot` |
| Command substitution | `$(rm ...)`, `` `rm ...` `` |
| Eval/exec | `eval`, `bash -c`, `sh -c` |
| Data exfiltration | `curl` with data flags (`-d`, `--data`), `wget --post-file` |

### Path Sandboxing

`file_read`, `file_write`, and `file_edit` validate that all paths resolve
within the current working directory. Paths that escape via `../` or
symlinks are rejected.

### URL Validation (SSRF Protection)

`http_request` and `web_fetch` validate URLs and resolve the hostname **exactly
once** before connecting. The resolved IP is pinned and used for the actual TCP
connection while the original hostname is sent as the `Host` header and TLS SNI
value — this prevents DNS rebinding (TOCTOU) attacks where an attacker causes a
hostname to resolve differently between the validation check and the connection.

Blocked targets:

- Non-HTTP schemes (only `http` and `https` allowed)
- Cloud metadata endpoints (`metadata.google.internal`, `169.254.169.254`)
- Localhost and loopback addresses
- Private IP ranges, link-local, and reserved addresses

### Permissions as Defense in Depth

Use the [permissions system](#permissions) to add an additional layer of
control. Deny tools the agent should never use and require approval for
destructive operations.

---

## Architecture

```
Agent
 └── ToolRegistry
      ├── Native tools (registered via @tool decorator or permission:)
      │    ├── sage.tools.builtins      (shell, file_read, file_write, http_request, memory_store, memory_recall)
      │    ├── sage.tools.file_tools    (file_edit)
      │    ├── sage.tools.web_tools     (web_fetch, web_search)
      │    └── custom modules via       (your own tools via extensions:)
      │
      ├── MCP tools (discovered from MCP servers)
      │    └── MCPClient → external MCP server
      │
      └── Permission handler (optional)
           └── PolicyPermissionHandler → category rules + patterns
```

**Execution flow:**

1. Agent sends tool schemas to the LLM provider.
2. LLM returns `ToolCall` objects (name + arguments).
3. `ToolRegistry.execute()` is called for each tool call:
   a. Permission check (if configured) — allow, deny, or ask.
   b. Route to MCP client (if MCP tool) or local function.
   c. For local functions: async functions are awaited directly; sync
      functions run in a thread via `asyncio.to_thread`.
   d. Result is stringified and returned.
4. Tool results are appended to the conversation as `tool` messages.
5. Loop continues until the LLM responds without tool calls or `max_turns`
   is reached.

**Key modules:**

| Module | Purpose |
|--------|---------|
| `sage.tools.decorator` | `@tool` decorator — generates `ToolSchema` from function signatures |
| `sage.tools.base` | `ToolBase` abstract class for stateful tools with setup/teardown |
| `sage.tools.registry` | `ToolRegistry` — central dispatch, permission checks, MCP routing |
| `sage.tools.builtins` | Core tools: shell, file_read, file_write, http_request, memory_store, memory_recall |
| `sage.tools.file_tools` | File manipulation: file_edit |
| `sage.tools.web_tools` | Web access: web_fetch, web_search |
| `sage.tools._security` | URL validation, DNS-pinned SSRF protection (`ResolvedURL`, `validate_and_resolve_url`) |
| `sage.tools._sandbox` | Shell sandbox backends (`NativeSandbox`, `BubblewrapSandbox`) and `make_sandboxed_shell` factory |
| `sage.permissions.policy` | Config-driven permission rules with pattern matching |
| `sage.permissions.interactive` | Interactive permission handler (prompts user on `ask`) |
| `sage.mcp.client` | MCP client — connects to servers, discovers and calls tools |
| `sage.mcp.server` | MCP server — exposes a ToolRegistry over MCP transport |

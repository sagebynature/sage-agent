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
  - [File Read](#file-read)
  - [File Write](#file-write)
  - [File Edit](#file-edit)
  - [Glob Find](#glob-find)
  - [Grep Search](#grep-search)
  - [Git Tools](#git-tools)
  - [Web Tools](#web-tools)
  - [Memory Tools](#memory-tools)
- [Configuring Tools](#configuring-tools)
  - [In Agent Frontmatter](#in-agent-frontmatter)
  - [In config.toml](#in-configtoml)
  - [Tool Name Resolution](#tool-name-resolution)
- [Permissions](#permissions)
  - [Permission Actions](#permission-actions)
  - [Rule Matching](#rule-matching)
  - [Pattern Matching](#pattern-matching)
  - [Examples](#permission-examples)
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
tools:
  - shell
  - file_read
  - file_edit
  - glob_find
  - grep_search
---

You are a helpful coding assistant.
```

Or load every built-in tool at once:

```yaml
tools:
  - sage.tools.builtins
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
[Security](#security) for the full list.

```
Agent calls: shell(command="ls -la src/")
→ "total 24\ndrwxr-xr-x 3 user user 4096 ..."
```

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

### Glob Find

**Name:** `glob_find`
**Module:** `sage.tools.file_tools`

Finds files matching a glob pattern. Uses
[`fd`](https://github.com/sharkdp/fd) when available, otherwise falls back
to Python `pathlib.glob`.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | `str` | yes | | Glob pattern (e.g. `*.py`, `**/*.ts`) |
| `path` | `str` | no | `"."` | Directory to search in |
| `max_results` | `int` | no | `200` | Maximum number of results |

**Returns:** Matching file paths, one per line.

---

### Grep Search

**Name:** `grep_search`
**Module:** `sage.tools.file_tools`

Searches file contents for a regex pattern. Uses
[ripgrep](https://github.com/BurntSushi/ripgrep) when available, otherwise
falls back to a pure-Python implementation.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | `str` | yes | | Regex pattern to search for |
| `path` | `str` | no | `"."` | Directory or file to search in |
| `glob` | `str` | no | `None` | File type filter (e.g. `*.py`) |
| `context_lines` | `int` | no | `0` | Lines of context around each match |
| `max_results` | `int` | no | `50` | Maximum matching lines |

**Returns:** Matches formatted as `path:line_number: content`.

---

### Git Tools

All git tools live in `sage.tools.git_tools`. Each wraps a git command and
returns its output.

#### git_status

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `repo_path` | `str` | no | `"."` | Repository path |

#### git_diff

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `staged` | `bool` | no | `false` | Show staged changes (`--cached`) |
| `target` | `str` | no | `None` | Diff against a branch or commit |
| `repo_path` | `str` | no | `"."` | Repository path |

#### git_commit

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `message` | `str` | yes | | Commit message |
| `files` | `list[str]` | no | `None` | Files to stage before committing |
| `repo_path` | `str` | no | `"."` | Repository path |

If `files` is provided, they are staged with `git add` before committing.
Otherwise, whatever is already staged is committed.

#### git_log

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `count` | `int` | no | `10` | Number of commits |
| `oneline` | `bool` | no | `true` | Use `--oneline` format |
| `repo_path` | `str` | no | `"."` | Repository path |

#### git_checkout

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `branch` | `str` | yes | | Branch name |
| `create` | `bool` | no | `false` | Create the branch (`-b`) |
| `repo_path` | `str` | no | `"."` | Repository path |

#### git_pr_create

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `title` | `str` | yes | | PR title |
| `body` | `str` | yes | | PR description |
| `base` | `str` | no | `"main"` | Base branch |
| `repo_path` | `str` | no | `"."` | Repository path |

Requires the [GitHub CLI](https://cli.github.com/) (`gh`) to be installed and
authenticated.

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

**Security:** SSRF protection blocks private IPs, loopback, link-local,
and cloud metadata endpoints. Only `http`/`https` schemes allowed.

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

The `tools:` list in your `AGENTS.md` frontmatter controls which tools the
agent has access to:

```yaml
---
name: my-agent
model: azure_ai/gpt-4o
tools:
  - shell
  - file_read
  - file_edit
  - glob_find
  - grep_search
  - git_status
  - git_diff
  - git_commit
  - git_log
  - web_search
  - web_fetch
---
```

### In config.toml

Set default tools for all agents in the `[defaults]` section of
`config.toml`. Individual agents can override this in their frontmatter or
in `[agents.<name>]` sections.

```toml
[defaults]
tools = ["sage.tools.builtins"]

[agents.researcher]
tools = ["file_read", "glob_find", "grep_search", "web_search", "web_fetch"]
```

The override is a full replacement — not a merge. If an agent specifies
`tools:` in its frontmatter, the default list is replaced entirely.

### Tool Name Resolution

The registry resolves tool names in this order:

| Format | Example | Resolution |
|--------|---------|------------|
| Bare built-in name | `shell` | `sage.tools.builtins` → registers `shell` |
| Bare extended name | `file_edit` | Looked up in internal map → `sage.tools.file_tools` → registers `file_edit` |
| `builtin` keyword | `builtin` | Registers **all** built-in tools from `sage.tools.builtins` |
| `builtin:<name>` | `builtin:shell` | Registers one built-in by name |
| Dotted module path | `sage.tools.git_tools` | Imports module → registers all `@tool` functions found |
| Module with selector | `myapp.tools:search` | Imports module → registers only `search` |
| Custom module path | `examples.custom_tools.tools` | Imports module → registers all `@tool` functions found |

**Built-in tool names** (resolved from `sage.tools.builtins`):
`shell`, `file_read`, `file_write`, `http_request`, `memory_store`,
`memory_recall`

**Extended tool names** (resolved from their respective modules):

| Name | Module |
|------|--------|
| `file_edit` | `sage.tools.file_tools` |
| `glob_find` | `sage.tools.file_tools` |
| `grep_search` | `sage.tools.file_tools` |
| `git_status` | `sage.tools.git_tools` |
| `git_diff` | `sage.tools.git_tools` |
| `git_commit` | `sage.tools.git_tools` |
| `git_log` | `sage.tools.git_tools` |
| `git_checkout` | `sage.tools.git_tools` |
| `git_pr_create` | `sage.tools.git_tools` |
| `web_search` | `sage.tools.web_tools` |
| `web_fetch` | `sage.tools.web_tools` |

---

## Permissions

Permissions control whether a tool call is allowed, denied, or requires user
approval. They are configured in the `permissions:` section of an agent's
frontmatter or `config.toml`.

### Permission Actions

| Action | Behavior |
|--------|----------|
| `allow` | Tool call proceeds without prompting |
| `deny` | Tool call is blocked; agent receives an error |
| `ask` | User is prompted for approval (default) |

### Rule Matching

Rules are evaluated in order. **The last matching rule wins.** This allows
you to set broad defaults first and add specific overrides after.

```yaml
permissions:
  default: deny          # deny everything by default
  rules:
    - tool: file_read    # then allow specific tools
      action: allow
    - tool: glob_find
      action: allow
    - tool: file_edit
      action: ask        # edits need approval
```

### Pattern Matching

Rules for the `shell` tool (or any tool that accepts a `command` argument)
can include `patterns:` for fine-grained control. Patterns use
[fnmatch](https://docs.python.org/3/library/fnmatch.html) glob syntax.
Again, **last match wins**.

```yaml
rules:
  - tool: shell
    action: deny
    destructive: true
    patterns:
      "git log *": allow
      "git diff *": allow
      "git status": allow
      "rm *": deny
      "rm -rf *": deny
      "*": deny
```

### Permission Examples

**Read-only reviewer** — can read files and git history but cannot modify anything:

```yaml
permissions:
  default: deny
  rules:
    - tool: file_read
      action: allow
    - tool: glob_find
      action: allow
    - tool: grep_search
      action: allow
    - tool: git_status
      action: allow
    - tool: git_diff
      action: allow
    - tool: git_log
      action: allow
```

See [`examples/permissions_agent/`](../examples/permissions_agent/) and
[`examples/safe_coder/`](../examples/safe_coder/) for full working examples.

**Supervised coder** — reads are free, edits need approval, shell is denied:

```yaml
permissions:
  default: deny
  rules:
    - tool: file_read
      action: allow
    - tool: glob_find
      action: allow
    - tool: grep_search
      action: allow
    - tool: file_edit
      action: ask
```

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
tools:
  - file_read
  - shell
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

**Option 1: Module path in frontmatter** (recommended)

Put your tools in a Python module and reference it by dotted path:

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
tools:
  - myproject.tools
```

The registry imports the module and registers every `@tool`-decorated
function and every `ToolBase` subclass it finds.

To register a single function from a module:

```yaml
tools:
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

`http_request`, `web_fetch`, and `web_search` validate URLs before making
requests. Blocked targets:

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
      ├── Native tools (registered via @tool decorator)
      │    ├── sage.tools.builtins    (shell, file_read, file_write, ...)
      │    ├── sage.tools.file_tools  (file_edit, glob_find, grep_search)
      │    ├── sage.tools.git_tools   (git_status, git_diff, ...)
      │    ├── sage.tools.web_tools   (web_fetch, web_search)
      │    └── custom modules         (your own tools)
      │
      ├── MCP tools (discovered from MCP servers)
      │    └── MCPClient → external MCP server
      │
      └── Permission handler (optional)
           └── PolicyPermissionHandler → rules + patterns
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
| `sage.tools.builtins` | Core tools: shell, file_read, file_write, http_request, memory |
| `sage.tools.file_tools` | File manipulation: file_edit, glob_find, grep_search |
| `sage.tools.git_tools` | Git operations: status, diff, commit, log, checkout, PR |
| `sage.tools.web_tools` | Web access: web_fetch, web_search |
| `sage.tools._security` | URL validation and SSRF protection |
| `sage.permissions.policy` | Config-driven permission rules with pattern matching |
| `sage.permissions.interactive` | Interactive permission handler (prompts user on `ask`) |
| `sage.mcp.client` | MCP client — connects to servers, discovers and calls tools |
| `sage.mcp.server` | MCP server — exposes a ToolRegistry over MCP transport |

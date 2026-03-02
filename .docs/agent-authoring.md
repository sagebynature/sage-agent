# Sage Agent Framework: Comprehensive Documentation

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Agent Definition by Markdown](#2-agent-definition-by-markdown)
3. [Agent Definition by Code](#3-agent-definition-by-code)
4. [Tool System](#4-tool-system)
5. [Skills System](#5-skills-system)
6. [Memory System](#6-memory-system)
7. [Hook System](#7-hook-system)
8. [Coordination](#8-coordination)
9. [Orchestration](#9-orchestration)
10. [Provider System](#10-provider-system)
11. [Permissions System](#11-permissions-system)
12. [Configuration System](#12-configuration-system)
13. [CLI & Entry Points](#13-cli--entry-points)
14. [Data Models](#14-data-models)
15. [Complete Examples](#15-complete-examples)

---

## 1. Architecture Overview

Sage is a Python framework for defining and running AI agents. Agents are configured via **Markdown files with YAML frontmatter** and/or constructed programmatically in Python. The framework is async-first, protocol-based, and supports 100+ LLM providers via LiteLLM.

### Core Components

```
Agent               <- Core orchestration loop (sage/agent.py)
|-- ProviderProtocol    <- LLM abstraction (sage/providers/)
|-- ToolRegistry        <- Tool dispatch (sage/tools/registry.py)
|-- MemoryProtocol      <- Persistent memory (sage/memory/)
|-- Skills              <- Injected knowledge (sage/skills/)
|-- MCPClient           <- External tool servers (sage/mcp/)
|-- Permissions         <- Access control (sage/permissions/)
+-- Subagents           <- Delegation to child agents
```

### Directory Structure

```
sage/
|-- agent.py                 # Core Agent class — run loop, hooks, compaction chain
|-- config.py                # Agent config loading/validation (Pydantic)
|-- models.py                # Pydantic data models
|-- main_config.py           # TOML-based main config system
|-- frontmatter.py           # YAML frontmatter parser
|-- exceptions.py            # Exception hierarchy
|-- research.py              # Pre-response research system (ResearchTrigger, run_research)
|-- __init__.py              # Public API exports
|-- cli/
|   |-- main.py              # Click CLI — sage agent / exec / eval / tool / init / tui
|   |-- tui.py               # Textual interactive TUI
|   |-- exit_codes.py        # SageExitCode IntEnum (exit codes 0–7)
|   +-- output.py            # OutputWriter — TextWriter, JSONLWriter, QuietWriter
|-- tools/
|   |-- base.py              # ToolBase abstract class
|   |-- decorator.py         # @tool decorator
|   |-- registry.py          # ToolRegistry dispatch
|   |-- dispatcher.py        # ToolDispatcher — parallel/sequential with timeout isolation
|   |-- builtins.py          # shell, file_read, file_write, http_request, memory_store, memory_recall
|   |-- file_tools.py        # file_edit
|   |-- web_tools.py         # web_search, web_fetch
|   |-- _security.py         # ResolvedURL, validate_and_resolve_url (SSRF + DNS-pinning)
|   +-- _sandbox.py          # NativeSandbox, BubblewrapSandbox, make_sandboxed_shell
|-- skills/
|   +-- loader.py            # Skill file loader
|-- orchestrator/
|   |-- pipeline.py          # Sequential execution (>> operator)
|   +-- parallel.py          # Parallel/race execution
|-- providers/
|   |-- base.py              # ProviderProtocol
|   +-- litellm_provider.py  # LiteLLM implementation
|-- memory/
|   |-- base.py              # MemoryProtocol
|   |-- embedding.py         # Embedding generation
|   |-- sqlite_backend.py    # SQLite + vector search
|   |-- file_backend.py      # File-based memory backend (JSON lines)
|   +-- compaction.py        # compact_messages, multi_part_compact, emergency_drop, deterministic_trim
|-- hooks/
|   |-- base.py              # HookEvent enum, HookHandler protocol
|   |-- registry.py          # HookRegistry — emit_void, emit_modifying
|   +-- builtin/
|       |-- credential_scrubber.py  # POST_TOOL_EXECUTE — redact secrets from tool outputs
|       |-- query_classifier.py     # PRE_LLM_CALL — route queries to different models
|       |-- follow_through.py       # POST_LLM_CALL — detect and retry bail-out phrases
|       +-- auto_memory.py          # PRE_LLM_CALL — inject recalled memories automatically
|-- coordination/
|   |-- messages.py          # MessageEnvelope, ReplyEnvelope typed message structs
|   |-- bus.py               # MessageBus — per-agent inboxes with TTL + idempotency
|   |-- cancellation.py      # CancellationScope — propagate cancel across async tasks
|   +-- session.py           # SessionManager, SessionState — session lifecycle
|-- parsing/
|   |-- tool_calls.py        # ChainParser — OpenAI JSON, XML, markdown, key-value formats
|   +-- json_repair.py       # Heuristic JSON fixer for malformed LLM output
|-- mcp/
|   |-- client.py            # MCP client
|   +-- server.py            # MCP server
|-- permissions/
|   |-- base.py              # PermissionProtocol
|   |-- policy.py            # Pattern-matching policy
|   +-- interactive.py       # Interactive prompting
+-- context/
    |-- token_budget.py      # Token budget management
    +-- fallback_table.py    # Static context-window size table (60+ models)
|-- eval/
|   |-- suite.py             # TestSuite, TestCase, EvalSettings, load_suite()
|   |-- assertions.py        # 11 assertion types + run_assertion()
|   |-- runner.py            # EvalRunner, CaseResult, EvalRunResult
|   |-- history.py           # EvalHistory — SQLite (~/.config/sage/eval_history.db)
|   +-- report.py            # Text/JSON/comparison formatters
```

### Execution Flow

```
User Input
    |
    v
Agent.run(input)
    |
    |-- Initialize MCP servers (first run only)
    |-- Initialize memory backend (first run only)
    |-- Recall relevant memories (or via auto_memory hook)
    |-- Build messages: [system + skills + memory + history + user]
    |
    |-- FOR turn in range(max_turns):
    |   |-- Emit PRE_LLM_CALL hook (model, messages, tool_schemas)
    |   |-- Call provider.complete(messages, tools)
    |   |-- Emit POST_LLM_CALL hook (response)
    |   |-- If no tool_calls -> DONE (return content)
    |   +-- For each tool_call (parallel if parallel_tool_execution=true):
    |       |-- Permission check
    |       |-- Execute via ToolRegistry or MCPClient
    |       |-- Emit POST_TOOL_EXECUTE hook (tool_name, arguments, result)
    |       +-- Append tool result to messages
    |
    |-- Store conversation to memory
    |-- Maybe compact history (token-aware):
    |       1. compact_messages (LLM summarization)
    |       2. emergency_drop (keep last N) — fallback
    |       3. deterministic_trim (slice to target) — always succeeds
    |-- Emit ON_COMPACTION hook (strategy, before_count, after_count)
    +-- Return final output

Agent.delegate(agent_name, task)
    |-- Emit ON_DELEGATION hook (target, input)
    |-- subagent.run(task)  [crash-isolated; returns error string on failure]
    +-- Return result
```

---

## 2. Agent Definition by Markdown

Agents are defined in `.md` files (conventionally named `AGENTS.md`) with YAML frontmatter and a markdown body. The frontmatter holds configuration; the body becomes the **system prompt**.

### File Format

```markdown
---
# YAML frontmatter = agent configuration
name: agent-name          # Required: unique identifier
model: gpt-4o             # Required: LLM model (litellm format)
description: A helper     # Optional: display-only, NOT sent to LLM
max_turns: 10             # Optional: max agentic loop iterations (default: 10)
max_depth: 3              # Optional: max delegation depth (default: 3)
permission: {...}         # Optional: tool access control by category
extensions: [...]         # Optional: custom tool module paths
memory: {...}             # Optional: persistent memory config
subagents: [...]          # Optional: child agents for delegation
mcp_servers: {...}        # Optional: MCP server connections (named dict)
model_params: {...}       # Optional: LLM parameters
context: {...}            # Optional: token budget management
---

<!-- Markdown body = system prompt sent to the LLM -->
You are a helpful AI assistant.

You have access to tools for file operations and web browsing.
Be concise and accurate.
```

**Key distinction**: `description` is metadata for display/discovery only. The markdown body below the frontmatter is what the LLM actually sees as its system prompt.

### Frontmatter Parsing (`sage/frontmatter.py`)

```python
def parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from raw text.
    Returns (metadata_dict, body_string). On error, returns ({}, full_text).
    """
```

The parser splits on `---` delimiters, extracts the YAML block via `yaml.safe_load()`, and returns the remaining text as the body.

### Frontmatter Fields Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Agent identifier |
| `model` | `str` | required* | LLM model in litellm format |
| `description` | `str` | `""` | Display-only metadata (not sent to LLM) |
| `max_turns` | `int` | `10` | Max agentic loop iterations |
| `max_depth` | `int` | `3` | Maximum subagent delegation depth. Prevents unbounded recursive delegation chains. Default: 3. |
| `permission` | `Permission` | `None` | Category-based tool access control |
| `extensions` | `list[str]` | `[]` | Custom tool module paths |
| `memory` | `MemoryConfig` | `None` | Persistent memory configuration |
| `subagents` | `list` | `[]` | Child agent references |
| `mcp_servers` | `dict[str, MCPServerConfig]` | `{}` | MCP server connections |
| `model_params` | `ModelParams` | `{}` | LLM generation parameters |
| `context` | `ContextConfig` | `None` | Token budget management |
| `sandbox` | `SandboxConfig` | `None` | Shell sandbox: `backend` (`auto`/`native`/`bubblewrap`/`seatbelt`/`docker`/`none`), `mode` (`read-only`/`workspace-write`/`full-access`), `enabled` (default `false`), `network` (default `true`) |
| `parallel_tool_execution` | `bool` | `true` | Run independent tool calls concurrently via `asyncio.gather` |
| `tool_timeout` | `float \| null` | `null` | Default timeout (seconds) for all tool calls; per-tool `@tool(timeout=N)` takes precedence |
| `tracing` | `TracingConfig` | `None` | OpenTelemetry tracing configuration (requires `pip install sage-agent[tracing]`) |
| `credential_scrubbing` | `CredentialScrubConfig` | `None` | Redact secrets from tool outputs via regex patterns and allowlist |
| `query_classification` | `QueryClassificationConfig` | `None` | Route queries to different models based on keyword/regex rules |
| `follow_through` | `FollowThroughConfig` | `None` | Detect LLM bail-out phrases and trigger retries |
| `research` | `ResearchConfig` | `None` | Pre-response research phase configuration |
| `session` | `SessionConfig` | `None` | Session lifecycle management |

*`model` can be inherited from main config defaults.

### Permission Configuration (Category-Based)

Instead of listing individual tools, you control access via **permission categories**. Each category controls which built-in tools are available:

```yaml
permission:
  read: allow              # Controls file_read
  edit: allow              # Controls file_write, file_edit
  shell: allow             # Controls shell
  web: allow               # Controls web_fetch, web_search, http_request
  memory: allow            # Controls memory_store, memory_recall
  task: allow              # Reserved for future task management
  git: allow               # Controls git_status, git_diff, git_log, git_commit, etc.
```

Values for each category: `"allow"` | `"deny"` | `"ask"` | `{pattern: action, ...}`

**Category-to-Tools Mapping:**
- `read: allow` -> registers `file_read`
- `edit: allow` -> registers `file_write`, `file_edit`
- `shell: allow` -> registers `shell`
- `web: allow` -> registers `web_fetch`, `web_search`, `http_request`
- `memory: allow` -> registers `memory_store`, `memory_recall`
- `task: allow` -> (reserved, no tools currently)
- `git: allow` -> registers `git_status`, `git_diff`, `git_log`, `git_commit`, `git_undo`, `git_branch`, `git_worktree_create`, `git_worktree_remove`, `snapshot_create`, `snapshot_restore`, `snapshot_list`

When a category is set to `"deny"`, its tools are not available to the LLM. When `"ask"`, the agent prompts for approval before executing. When set to a dict, you can specify per-pattern rules:

```yaml
permission:
  read: allow                      # All file_read calls allowed
  shell:                           # Per-pattern shell control
    "*": ask                        # Default: ask for permission
    "git status": allow             # Exception: always allow git status
    "git diff*": allow              # Wildcard pattern: allow git diff
    "git log*": allow               # Wildcard pattern: allow git log
```

### Extensions (Custom Tools)

To register custom tools from a Python module, use the `extensions` field:

```yaml
extensions:
  - examples.custom_tools.tools           # All @tool-decorated functions in module
  - myapp.tools.database                  # Another custom tools module
```

Each extension is a Python module path containing functions decorated with `@tool`. They are automatically discovered and registered.

### Subagent References

Three styles of subagent declaration:

```yaml
subagents:
  # 1. Directory reference (loads AGENTS.md from directory)
  - research_agent

  # 2. Explicit file path
  - config: helpers/critic.md

  # 3. Inline definition (must be fully specified)
  - name: inline-helper
    model: gpt-4o-mini
```

### Memory Configuration

```yaml
memory:
  backend: sqlite                        # "sqlite" (default) or "file" (JSON-lines flat file)
  path: memory.db                        # Database file path (or .jsonl path for file backend)
  embedding: text-embedding-3-large      # Embedding model (litellm format)
  compaction_threshold: 50               # Messages before compaction triggers
  auto_load: false                       # Inject recalled memories as system message before each LLM call
  auto_load_top_k: 5                     # How many memories to inject when auto_load is true
  vector_search: auto                    # "auto" | "sqlite_vec" | "numpy"
                                         # auto: use sqlite-vec if available, numpy fallback
                                         # sqlite_vec: require extension (pip install sage-agent[vec])
                                         # numpy: force O(n) numpy path
  relevance_filter: none                 # "none" | "length" | "llm"
                                         # none: store every exchange (default)
                                         # length: skip if exchange < min_exchange_length chars
                                         # llm: ask provider to score; skip below relevance_threshold
  min_exchange_length: 100               # Minimum chars to store (length filter only)
  relevance_threshold: 0.5              # Min LLM score to store (llm filter only, 0.0–1.0)
```

**Backends:**
- `sqlite` (default) — SQLite database with optional `sqlite-vec` ANN search; falls back to numpy cosine similarity
- `file` — JSON-lines flat file (`FileMemory`); simpler, no database; suitable for lightweight or read-only deployments

### MCP Server Configuration

```yaml
mcp_servers:
  # stdio transport (subprocess)
  filesystem:
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    env: { KEY: value }

  # SSE transport (HTTP)
  remote-tools:
    transport: sse
    url: http://localhost:8080/sse
```

### Model Parameters

```yaml
model_params:
  temperature: 0.7
  max_tokens: 4096
  top_p: 1.0
  top_k: 40
  frequency_penalty: 0.0
  presence_penalty: 0.0
  seed: 42
  stop: ["END"]
  timeout: 120.0
  response_format: { type: json_object }
  num_retries: 3       # Automatic retries on transient provider errors (forwarded to litellm)
  retry_after: 1.0     # Base back-off interval in seconds between retries
```

Only fields that are set are forwarded; omitted fields use provider defaults.

### Context Management

```yaml
context:
  compaction_threshold: 0.75   # Fraction of context window triggering compaction
  reserve_tokens: 4096         # Tokens reserved for model output
  prune_tool_outputs: true     # Truncate large tool outputs
  tool_output_max_chars: 5000  # Max chars per tool output
```

### Tracing Configuration

Requires `pip install sage-agent[tracing]` (opentelemetry-api + sdk).

```yaml
tracing:
  enabled: true
  service_name: my-agent         # Appears as service.name in spans
  exporter: console              # "none" | "console" | "otlp"
                                 # otlp requires opentelemetry-exporter-otlp-proto-grpc
```

When enabled, sage emits nested spans:

```
agent.run
  ├── llm.complete        (model, message_count, prompt_tokens, completion_tokens)
  ├── tool.execute        (tool.name, tool.args)
  └── memory.recall       (query_length, limit, result_count)
      memory.store        (content_length)
```

All instrumentation is zero-cost when `tracing:` is not configured or `opentelemetry-api` is not installed.

### Git Configuration

Git integration configuration. When `auto_snapshot` is enabled (default), the agent creates a lightweight restore point before file edits so changes can be rolled back.

```yaml
git:
  auto_snapshot: true              # Create restore point before file edits (default: true)
  auto_commit_dirty: false         # Auto-commit dirty working tree on start
  auto_commit_edits: false         # Auto-commit after each file edit
```

### Identity Configuration

Optional AIEOS personality/identity injection. When configured, loads a YAML persona definition and injects personality traits (neural matrix weights, text style, idiolect, biography) into the system prompt.

```yaml
identity:
  format: aieos                    # "aieos" or "none" (default: "none")
  file: persona.yaml               # Path to AIEOS v1.2 identity YAML
```

---

## 3. Agent Definition by Code

### Constructor

```python
from sage import Agent, tool

agent = Agent(
    name="calc",                # Required
    model="gpt-4o",             # Required
    description="Calculator",   # Display-only
    body="You are a calculator assistant.",  # System prompt
    tools=[add_func],           # @tool functions, ToolBase instances, or module strings
    max_turns=10,
    model_params={"temperature": 0.1},
    skills=None,                # list[Skill]
    mcp_clients=None,           # list[MCPClient]
    memory=None,                # MemoryProtocol
    subagents=None,             # dict[str, Agent]
    provider=None,              # ProviderProtocol (defaults to LiteLLMProvider)
    compaction_threshold=50,
)
```

### Factory Method -- `from_config()`

```python
# From a markdown file
agent = Agent.from_config("path/to/AGENTS.md")

# From a directory (auto-finds AGENTS.md)
agent = Agent.from_config("path/to/agent_dir/")

# With main config for defaults/overrides
from sage.main_config import load_main_config, resolve_main_config_path
main_config = load_main_config(resolve_main_config_path())
agent = Agent.from_config("AGENTS.md", central=main_config)
```

The `from_config()` method (`sage/agent.py:112-119`):
1. Resolves the path (directory -> `AGENTS.md` inside it)
2. Calls `load_config()` which parses frontmatter, merges with main config, validates via Pydantic
3. Calls `_from_agent_config()` which recursively builds the agent tree (subagents, MCP clients, memory, permissions, skills)

### Running an Agent

```python
# Non-streaming (returns full response)
result = await agent.run("What is 2 + 3?")

# Streaming (yields text chunks)
async for chunk in agent.stream("What is 2 + 3?"):
    print(chunk, end="")

# Structured output — parse response into a Pydantic model
from pydantic import BaseModel

class Summary(BaseModel):
    title: str
    points: list[str]

summary = await agent.run("Summarise the GIL", response_model=Summary)
print(summary.title)   # Summary is a Summary instance, not a str

# Multi-turn (history accumulates across calls)
r1 = await agent.run("My name is Alice")
r2 = await agent.run("What is my name?")  # Sees prior context

# Reset conversation
agent.clear_history()

# Clean up resources
await agent.close()
```

When `response_model` is provided, sage injects the Pydantic JSON schema as a system message, strips any markdown code fences the LLM may add, and calls `model_validate_json()` on the response. `pydantic.ValidationError` is raised if the output cannot be parsed.

### Delegation to Subagents

When an agent has subagents, a `delegate` tool is auto-registered (`sage/agent.py:511-555`):

```python
parent = Agent(
    name="orchestrator",
    model="gpt-4o",
    body="You are an orchestrator. Use delegate to assign tasks.",
    subagents={
        "researcher": researcher_agent,
        "writer": writer_agent,
    },
)
# The LLM can now call: delegate(agent_name="researcher", task="Find info about X")
```

The generated tool schema includes:
- Enum of available subagent names
- Description listing each subagent and its description

### Token Management & Compaction

The agent automatically:
1. Detects context window size from litellm model info (`sage/agent.py:439-456`)
2. Tracks token usage via `litellm.token_counter()` (`sage/agent.py:458-464`)
3. Compacts history when either:
   - Token usage exceeds 80% of context window
   - Message count exceeds `compaction_threshold`
   - At least 2 turns have passed since last compaction

Compaction summarizes older messages via the LLM while preserving the 10 most recent messages.

---

## 4. Tool System

### 4.1 The `@tool` Decorator (`sage/tools/decorator.py`)

Converts any function into an LLM-callable tool by inspecting its signature, type hints, and docstring to auto-generate JSON Schema:

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
async def fetch_data(url: str, timeout: float = 30.0) -> str:
    """Fetch data from a URL."""
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=timeout)
        return resp.text
```

**What the decorator does:**
1. Inspects function signature via `inspect.signature()`
2. Resolves type hints via `typing.get_type_hints()`
3. Converts each parameter's type annotation to JSON Schema
4. Stores the schema as `fn.__tool_schema__` (a `ToolSchema` instance)
5. Returns the function unchanged (no wrapping)

**Type mapping** (`sage/tools/decorator.py:15-22`):

| Python Type | JSON Schema |
|-------------|-------------|
| `str` | `"string"` |
| `int` | `"integer"` |
| `float` | `"number"` |
| `bool` | `"boolean"` |
| `list[T]` | `{"type": "array", "items": ...}` |
| `dict[K, V]` | `{"type": "object", "additionalProperties": ...}` |
| `Optional[T]` | Unwrapped to `T` (not required) |
| Pydantic `BaseModel` | `model.model_json_schema()` |
| `Any` / missing | `"string"` (fallback) |

### 4.2 ToolBase -- Stateful Tools (`sage/tools/base.py`)

For tools that need shared state or lifecycle management:

```python
from sage.tools import ToolBase, tool

class DatabaseTools(ToolBase):
    def __init__(self, connection_string: str):
        self.conn_str = connection_string
        self.db = None
        super().__init__()  # Collects @tool methods

    async def setup(self):
        """Called before first use."""
        self.db = await connect(self.conn_str)

    async def teardown(self):
        """Called on cleanup."""
        await self.db.close()

    @tool
    def query(self, sql: str) -> str:
        """Execute a SQL query."""
        return str(self.db.execute(sql))

    @tool
    async def insert(self, table: str, data: dict) -> str:
        """Insert a row into a table."""
        await self.db.insert(table, data)
        return "Inserted"

# Usage
db_tools = DatabaseTools("sqlite:///data.db")
agent = Agent(name="db-agent", model="gpt-4o", tools=[db_tools])
```

`ToolBase.__init__()` scans `dir(self)` for any method with a `__tool_schema__` attribute (set by `@tool`) and stores them in `self._tools`.

### 4.3 ToolRegistry (`sage/tools/registry.py`)

Central dispatch system that manages tool functions, schemas, permissions, and MCP tools:

```python
registry = ToolRegistry()

# Register a @tool function
registry.register(calculate)

# Register a ToolBase instance (all its @tool methods)
registry.register(db_tools)

# Load from module path (via permission categories or extensions)
registry.register_from_permissions(permission_config)  # Auto-register by permission
registry.load_from_module("sage.tools.builtins")       # All built-ins
registry.load_from_module("sage.tools.builtins:shell") # Specific tool
registry.load_from_module("myapp.tools")               # Custom module
registry.load_from_module("myapp.tools:search")        # Specific attribute

# Register MCP-discovered tool
registry.register_mcp_tool(schema, mcp_client)

# Get all schemas (for passing to LLM)
schemas = registry.get_schemas()  # list[ToolSchema]

# Execute a tool call
result = await registry.execute("calculate", {"expression": "2+3"})
```

**Execution flow** (`sage/tools/registry.py:73-116`):
1. Look up function by name (local tools) or MCP client (MCP tools)
2. Run permission check if handler is configured
3. If MCP tool -> `mcp_client.call_tool(name, arguments)`
4. If async function -> `await fn(**arguments)`
5. If sync function -> `await asyncio.to_thread(fn, **arguments)`
6. Return `str(result)`

### 4.4 Built-in Tools

| Name | Module | Description |
|------|--------|-------------|
| `shell` | `sage.tools.builtins` | Execute shell commands |
| `file_read` | `sage.tools.builtins` | Read file contents |
| `file_write` | `sage.tools.builtins` | Write file contents |
| `http_request` | `sage.tools.builtins` | Make HTTP requests |
| `memory_store` | `sage.tools.builtins` | Store to memory |
| `memory_recall` | `sage.tools.builtins` | Recall from memory |
| `file_edit` | `sage.tools.file_tools` | Edit files with replacements |
| `web_search` | `sage.tools.web_tools` | Web search |
| `web_fetch` | `sage.tools.web_tools` | Fetch web page |

---

## 5. Skills System

Skills are **reusable knowledge documents** (not executable code) injected into the agent's system prompt. They guide agent behavior without being tools.

### Skill File Format

```markdown
---
name: code-review
description: Systematic checklist for reviewing code quality
---

When reviewing code, work through these categories in order:

1. **Correctness** -- Does the logic match the stated intent?
2. **Clarity** -- Are names descriptive?
3. **Error handling** -- Are errors caught at the right level?
4. **Performance** -- Any obvious O(n^2) loops?
5. **Security** -- Any injection risks?
6. **Tests** -- Does the change come with tests?

For each issue found, state: the location, the problem, and a concrete fix.
```

### Skill Loading (`sage/skills/loader.py`)

```python
from sage.skills.loader import load_skill, load_skills_from_directory

# Load a single skill
skill = load_skill("skills/code-review/SKILL.md")
# -> Skill(name="code-review", description="...", content="...")

# Load all skills from a directory
skills = load_skills_from_directory("skills/")
```

**Directory layouts supported:**
- **Flat**: `skills/code-review.md`
- **Per-skill directory**: `skills/code-review/skill.md` or `skills/code-review/SKILL.md` or `skills/code-review/code-review.md`

Skills with executable scripts (like the `data-cruncher` or `crypto-toolkit` examples) place both the skill markdown and scripts in the same directory. The markdown explains *when and how* to invoke the scripts via the `shell` tool.

### How Skills are Injected

Since v1.11.0, skills use a **two-phase lazy-loading** approach:

**Phase 1 -- System Prompt Catalog:** When building messages, only a lightweight catalog is injected into the system prompt. Each skill is listed with just its name and one-line description:

```
[System message]
  Body text (from markdown below frontmatter)

  ## Available Skills

  - **code-review**: Systematic checklist for reviewing code quality
  - **debugging**: Step-by-step debugging methodology

  Use the `use_skill` tool to load a skill's full instructions.

[Memory context]
[Conversation history]
[User message]
```

**Phase 2 -- On-Demand Loading:** The `use_skill(name)` tool is automatically registered when an agent has skills. When the LLM decides a skill is relevant, it calls `use_skill` to load the full markdown content. On first call for a given skill, the complete instructions are returned. Subsequent calls for the same skill return a short "already loaded" notice.

### Lazy Skill Loading via `use_skill`

When an agent has skills, only a lightweight catalog (name + one-line description) is included in the system prompt. The `use_skill(name)` tool is automatically registered, allowing the LLM to load a skill's full markdown instructions on demand. On first call for a given skill, the full content is returned. Subsequent calls for the same skill return a short "already loaded" notice. The tool's `name` parameter is constrained to an enum of valid skill names.

### Skill Pool Resolution

Skills are resolved from a **global pool** shared across all agents. The pool directory is determined via a waterfall (first existing path wins):

1. `skills_dir` in `config.toml` (explicit path)
2. `./skills/` (current working directory)
3. `~/.agents/skills/`
4. `~/.claude/skills/`
5. No skills (if none of the above exist)

Each agent in `[agents.<name>]` of `config.toml` can optionally restrict its skills via a named allowlist:
```toml
[agents.my-agent]
skills = ["git-master", "terraform"]  # only these skills are injected
```
Omitting `skills` (or setting it to `null`) injects the full pool. Subagents always receive the full unfiltered pool and apply their own allowlist independently.

---

## 6. Memory System

### MemoryProtocol (`sage/memory/base.py`)

```python
class MemoryProtocol(Protocol):
    async def store(self, content: str, metadata: dict | None = None) -> str:
        """Store content, return memory ID."""

    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Recall top-K memories by semantic similarity."""

    async def compact(self, messages: list[Message]) -> list[Message]:
        """Compact message history."""

    async def clear(self) -> None:
        """Delete all memories."""
```

### SQLite Memory Backend

Uses SQLite for storage with embedding vectors for semantic search:

```python
from sage.memory.embedding import LiteLLMEmbedding
from sage.memory.sqlite_backend import SQLiteMemory

embedding = LiteLLMEmbedding("text-embedding-3-large")
memory = SQLiteMemory(path="memory.db", embedding=embedding)
await memory.initialize()

# Store
await memory.store("User asked about Python decorators. I explained @tool.")

# Recall (cosine similarity search)
entries = await memory.recall("How do decorators work?", limit=5)
```

### Memory Tools

- `memory_store(key, value)` -- stores `"key: value"` as a single embedded document. Returns `"Stored: {key}"`.
- `memory_recall(query)` -- retrieves the top-5 semantically similar entries. Returns a bulleted list of matches.
- `memory_forget(memory_id)` -- deletes a specific memory entry by its ID. Registered alongside `memory_store` and `memory_recall` when a memory backend is configured.

### Memory in Agent Lifecycle

1. **Recall**: Before each `run()`, memories relevant to the input are recalled and prepended as a system message
2. **Store**: After each `run()`, the user-assistant exchange is stored: `"User: {input}\nAssistant: {output}"`
3. **Compaction**: When history grows too large, the compaction chain runs (see Agent section)

---

## 7. Hook System

Hooks let you intercept and extend agent behavior at well-defined lifecycle points without modifying core code. Every hook is async; errors are caught and logged without crashing the agent.

### HookEvent (`sage/hooks/base.py`)

```python
class HookEvent(str, enum.Enum):
    PRE_LLM_CALL       = "pre_llm_call"       # before provider.complete()
    POST_LLM_CALL      = "post_llm_call"       # after provider.complete()
    PRE_TOOL_EXECUTE   = "pre_tool_execute"    # before tool dispatch
    POST_TOOL_EXECUTE  = "post_tool_execute"   # after tool dispatch
    ON_DELEGATION      = "on_delegation"       # before subagent.run()
    ON_COMPACTION      = "on_compaction"       # after history compaction
    ON_DELEGATION_COMPLETE = "on_delegation_complete"  # after subagent.run()
    ON_LLM_STREAM_DELTA   = "on_llm_stream_delta"     # each streaming token/chunk
    PRE_MEMORY_RECALL  = "pre_memory_recall"
    POST_MEMORY_STORE  = "post_memory_store"
    PRE_COMPACTION     = "pre_compaction"
    POST_COMPACTION    = "post_compaction"
```

### HookRegistry (`sage/hooks/registry.py`)

```python
from sage.hooks.registry import HookRegistry
from sage.hooks.base import HookEvent

hr = HookRegistry()

# Void handler (side effects only — runs in parallel with other void handlers)
async def log_calls(event: HookEvent, data: dict) -> None:
    print(f"[{event}] model={data.get('model')}")

# Modifying handler (can mutate data — runs sequentially, receives prior output)
async def reroute(event: HookEvent, data: dict) -> dict | None:
    if "python" in str(data.get("messages", "")):
        data["model"] = "gpt-4o"
        return data
    return None  # no change

hr.register(HookEvent.PRE_LLM_CALL, log_calls)
hr.register(HookEvent.PRE_LLM_CALL, reroute)

agent = Agent(name="a", model="gpt-4o", hook_registry=hr)
```

**Emission modes:**
- `emit_void(event, data)` — fires all registered handlers in parallel (`asyncio.gather`); return values are ignored
- `emit_modifying(event, data)` — fires handlers sequentially; each handler receives the (possibly mutated) output of the previous one; returning `None` passes data unchanged

### Built-in Hooks

#### Credential Scrubbing (`sage/hooks/builtin/credential_scrubber.py`)

Redacts secrets from tool outputs on `POST_TOOL_EXECUTE`:

```yaml
credential_scrubbing:
  enabled: true
  patterns: ["sk-[A-Za-z0-9]{20,}", "Bearer [A-Za-z0-9._-]+"]
  allowlist: ["sk-test"]          # substrings that are never redacted
```

#### Query Classification (`sage/hooks/builtin/query_classifier.py`)

Routes queries to different models on `PRE_LLM_CALL`:

```yaml
query_classification:
  rules:
    - keywords: ["python", "typescript"]
      patterns: [".*code.*review.*"]
      priority: 10
      target_model: gpt-4o
    - keywords: ["summarize", "tldr"]
      patterns: []
      priority: 5
      target_model: gpt-4o-mini
```

Rules are sorted by `priority` descending; first match wins.

#### Follow-Through Guardrail (`sage/hooks/builtin/follow_through.py`)

Detects bail-out phrases in assistant responses and requests a retry on `POST_LLM_CALL`:

```yaml
follow_through:
  enabled: true
  patterns: ["I cannot", "I'm unable", "I don't have access"]
  # max_retries defaults to 2 — set via code if needed
```

Default bail-out patterns: `"I can't/cannot do/perform/execute"`, `"I'm unable to"`, `"I don't have the ability/access/permission"`, `"Let me know if you'd like me to"`, `"Would you like me to"`, `"I cannot directly"`.

#### Auto Memory (`sage/hooks/builtin/auto_memory.py`)

Injects recalled memories as a system message before each LLM call, when `auto_load: true` is set in the memory config:

```yaml
memory:
  backend: sqlite
  path: memory.db
  auto_load: true
  auto_load_top_k: 5
```

### Typed Event Subscription

The `agent.on(EventClass, handler)` method provides a typed alternative to raw hook registration. Event classes in `sage.events` map to underlying `HookEvent` values:

| Event Class | Hook Event | Fields |
|-------------|-----------|--------|
| `ToolStarted` | `PRE_TOOL_EXECUTE` | `name`, `arguments`, `turn` |
| `ToolCompleted` | `POST_TOOL_EXECUTE` | `name`, `result`, `duration_ms` |
| `LLMTurnStarted` | `PRE_LLM_CALL` | `turn`, `model`, `n_messages` |
| `LLMTurnCompleted` | `POST_LLM_CALL` | `turn`, `usage`, `n_tool_calls` |
| `DelegationStarted` | `ON_DELEGATION` | `target`, `task` |
| `DelegationCompleted` | `ON_DELEGATION_COMPLETE` | `target`, `result` |
| `LLMStreamDelta` | `ON_LLM_STREAM_DELTA` | `delta`, `turn` |

```python
from sage.events import ToolCompleted

async def log_tools(e: ToolCompleted) -> None:
    print(f'{e.name} took {e.duration_ms:.0f}ms')

agent.on(ToolCompleted, log_tools)
```

---

## 8. Coordination

Primitives for multi-agent coordination and session management.

### MessageBus (`sage/coordination/bus.py`)

```python
from sage.coordination.bus import MessageBus
from sage.coordination.messages import MessageEnvelope

bus = MessageBus(max_inbox_size=100, ttl_seconds=300.0)

msg = MessageEnvelope(
    sender="orchestrator",
    recipient="worker",
    topic="task",
    payload={"job": "summarize doc X"},
)

# Send (returns False if duplicate — idempotency guard)
delivered = bus.send(msg)

# Receive up to 10 live (non-expired) messages
msgs = bus.receive("worker", limit=10)

# Broadcast to all known inboxes
count = bus.broadcast(msg)

# Peek count without consuming
pending = bus.peek("worker")
```

Messages expire after `ttl_seconds` and are moved to a dead-letter collection.

### CancellationScope (`sage/coordination/cancellation.py`)

```python
from sage.coordination.cancellation import CancellationScope

root = CancellationScope()
child = root.child()

# Cancel propagates to child
root.cancel()
assert child.is_cancelled

# check() raises asyncio.CancelledError if cancelled
try:
    child.check()
except asyncio.CancelledError:
    pass
```

### SessionManager (`sage/coordination/session.py`)

```python
from sage.coordination.session import SessionManager

mgr = SessionManager()

session = mgr.create("my-agent", metadata={"user_id": "u123"})
print(session.id, session.status)  # "active"

mgr.get(session.id)                # lookup by id
mgr.list_sessions(agent_name="my-agent")
mgr.destroy(session.id)            # returns True if found

print(mgr.count())
```

---

## 9. Orchestration

### Sequential Pipeline (`sage/orchestrator/pipeline.py`)

Output of one agent feeds as input to the next:

```python
from sage import Pipeline

# Using constructor
pipeline = Pipeline([researcher, summarizer, reviewer])
result = await pipeline.run("Analyze the Python GIL")

# Using >> operator
pipeline = researcher >> summarizer >> reviewer
result = await pipeline.run("Analyze the Python GIL")

# Streaming — intermediate agents run(), final agent streams
async for chunk in pipeline.stream("Analyze the Python GIL"):
    print(chunk, end="")
```

`stream()` runs every agent except the last using `run()`, then streams the final agent's output. Single-agent and empty pipelines are handled gracefully.

### Parallel Execution (`sage/orchestrator/parallel.py`)

```python
from sage import Orchestrator

# Same input to all agents
results = await Orchestrator.run_parallel(
    [agent_a, agent_b, agent_c],
    "What is the capital of France?"
)
for r in results:
    print(f"{r.agent_name}: {'OK' if r.success else r.error}")

# Different inputs
results = await Orchestrator.run_parallel(
    [agent_a, agent_b],
    ["Input for A", "Input for B"]
)

# Race mode -- first to succeed wins, others are cancelled and awaited
winner = await Orchestrator.run_race(
    [fast_agent, slow_agent, fallback_agent],
    "Answer this quickly"
)
print(f"Winner: {winner.agent_name}: {winner.output}")
```

Cancelled losing agents are fully awaited before `run_race()` returns, ensuring their `finally` blocks and resource cleanup (open connections, file handles) run to completion.

### Autonomous Delegation (LLM-Driven)

When subagents are defined, the LLM decides when to delegate:

```yaml
---
name: orchestrator
model: gpt-4o
subagents:
  - research_agent
  - summarize_agent
---
You are an orchestrator. Delegate research tasks to research_agent
and summarization to summarize_agent.
```

The framework auto-generates a `delegate(agent_name, task)` tool. The LLM calls it naturally as part of its reasoning loop.

---

## 10. Provider System

### ProviderProtocol (`sage/providers/base.py`)

```python
@runtime_checkable
class ProviderProtocol(Protocol):
    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: object,
    ) -> CompletionResult: ...

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: object,
    ) -> AsyncIterator[StreamChunk]: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

### LiteLLM Provider

Supports 100+ LLM backends through litellm:

```python
from sage import LiteLLMProvider

# Provider is created automatically by Agent, but can be explicit:
provider = LiteLLMProvider("gpt-4o", temperature=0.7)
provider = LiteLLMProvider("azure_ai/gpt-4o")
provider = LiteLLMProvider("anthropic/claude-sonnet-4-20250514")
provider = LiteLLMProvider("ollama/llama3")

agent = Agent(name="a", model="gpt-4o", provider=provider)
```

If no provider is supplied to the Agent constructor, `LiteLLMProvider(model)` is used by default.

---

## 11. Permissions System

### Permission Categories and Actions

Access control is based on **tool categories**, each with one of four actions:

```python
"allow"  # Tool calls proceed
"deny"   # Tool calls are blocked (raises PermissionError)
"ask"    # Interactive prompt (falls back to allow if no handler)
# Or a dict mapping patterns to actions (for pattern-based control)
```

### Category-Based Permission Configuration

```yaml
permission:
  read: allow              # file_read allowed
  edit: deny               # file_write, file_edit denied
  shell:                   # Per-pattern shell rules
    "*": ask               # Default: ask
    "git status": allow    # Exception: allow git status
    "git diff*": allow     # Wildcard: allow git diff*
```

Categories are evaluated by `PolicyPermissionHandler` (`sage/permissions/policy.py`). Permission checks happen inside `ToolRegistry.execute()` before dispatch.

### How Categories Map to Tools

Built-in tool categories (via ToolRegistry):
- `read: allow` -> registers `file_read`
- `edit: allow` -> registers `file_write`, `file_edit`
- `shell: allow` -> registers `shell`
- `web: allow` -> registers `web_fetch`, `web_search`, `http_request`
- `memory: allow` -> registers `memory_store`, `memory_recall`
- `git: allow` -> registers `git_status`, `git_diff`, `git_log`, `git_commit`, `git_undo`, `git_branch`, `git_worktree_create`, `git_worktree_remove`, `snapshot_create`, `snapshot_restore`, `snapshot_list`

When a category is `"deny"`, its tools become invisible to the LLM (not registered).

---

## 12. Configuration System

### Three-Tier Override System

```
Agent .md frontmatter     <- highest priority
[agents.<name>] in TOML   <- per-agent overrides
[defaults] in TOML         <- global defaults (lowest)
```

### Main Config (TOML) -- `config.toml`

```toml
# Optional: global skills directory
# skills_dir = "/path/to/skills"

[defaults]
model = "azure_ai/gpt-4o"
max_turns = 10

[defaults.model_params]
temperature = 0.7
max_tokens = 4096

[defaults.permission]
read = "allow"
shell = "ask"

[defaults.context]
compaction_threshold = 0.75
reserve_tokens = 4096

[agents.researcher]
model = "azure_ai/kimi-k2.5"
max_turns = 20

[agents.researcher.model_params]
temperature = 0.0
max_tokens = 8192

[agents.researcher.memory]
backend = "sqlite"
path = "memory.db"
embedding = "text-embedding-3-large"

# Optional: limit this agent to a subset of the global skill pool
# skills = ["git-master", "terraform"]
```

### Config Resolution (`sage/main_config.py`)

Config file is located via waterfall:
1. `--config` CLI argument
2. `SAGE_CONFIG_PATH` environment variable
3. `./config.toml` (current working directory)
4. `~/.config/sage/config.toml`

Merge function (`sage/main_config.py:133-162`):
```python
def merge_agent_config(metadata, central, agent_name):
    # 1. Start with central.defaults
    merged = central.defaults.model_dump(exclude_none=True)
    # 2. Layer agent-specific overrides
    if agent_name in central.agents:
        merged.update(central.agents[agent_name].model_dump(exclude_none=True))
    # 3. Layer frontmatter (highest priority)
    merged.update(metadata)
    return merged
```

---

## 13. CLI & Entry Points

Entry point defined in `pyproject.toml`: `sage = "sage.cli.main:cli"`

### Commands

```bash
# Run an agent
sage agent run AGENTS.md -i "Hello!"
sage agent run AGENTS.md -i "Hello!" --stream

# Run all subagents in parallel
sage agent orchestrate AGENTS.md -i "Research topic X"

# Validate config without running
sage agent validate AGENTS.md

# List agents in a directory
sage agent list examples/

# List tools for an agent
sage tool list AGENTS.md

# Scaffold a new agent
sage init --name my-agent --model gpt-4o

# Interactive TUI
sage tui --agent-config AGENTS.md

# Global options
sage --config path/to/config.toml --verbose agent run ...
```
### `sage exec` — Headless & CI Execution

Run an agent in a non-interactive, headless mode suitable for scripts and CI/CD pipelines. Supports structured output and timeout isolation.

```bash
sage exec AGENTS.md -i "task" [-o text|jsonl|quiet] [--timeout N] [--yes]
```

**Output Formats (`-o` / `--output`):**
- `text` (default): Human-readable streaming text output.
- `jsonl`: One JSON object per event (llm_call, tool_call, result). Ideal for programmatic consumption.
- `quiet`: No output to stdout; only exit codes and logs (if configured).

**Exit Codes:**
Defined in `sage.cli.exit_codes.SageExitCode`:
- `0`: SUCCESS
- `1`: ERROR (Generic failure)
- `2`: CONFIG_ERROR (Validation failure)
- `3`: PROVIDER_ERROR (LLM timeout/failure)
- `4`: TOOL_ERROR (Tool execution failure)
- `5`: PERMISSION_DENIED (User or policy denied tool)
- `6`: TIMEOUT (Global execution timeout reached)
- `7`: CANCELLED (Interrupt or signal)

### `sage eval` — Evaluation Framework

Manage and execute evaluation suites to benchmark agent quality and performance.

```bash
# Run a suite and report metrics
sage eval run suite.yaml [--min-pass-rate 0.9] [--runs N]

# Validate suite YAML syntax
sage eval validate suite.yaml

# Browse SQLite run history
sage eval history [--suite NAME] [--last N]

# Compare two run results side-by-side
sage eval compare <run-id-1> <run-id-2>

# Discover suite files in a directory
sage eval list [directory]
```

Evaluation results are stored in `~/.config/sage/eval_history.db` by default.

---

## 14. Data Models (`sage/models.py`)

```python
class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)

class ToolSchema(BaseModel):
    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)

class CompletionResult(BaseModel):
    message: Message
    usage: Usage = Field(default_factory=Usage)
    raw_response: Any = None

class StreamChunk(BaseModel):
    delta: str | None = None
    finish_reason: str | None = None
    tool_calls: list[ToolCall] | None = None
    usage: Usage | None = None

class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
```

### Exception Hierarchy

```
SageError                    # Base
|-- ProviderError            # LLM provider failures
|-- ConfigError              # Config parsing/validation
|-- ToolError                # Tool execution failures
|-- SageMemoryError          # Memory backend failures
+-- PermissionError          # Permission denials
```

---

## 15. Complete Examples

### Minimal Agent

```markdown
---
name: assistant
model: azure_ai/gpt-4o
max_turns: 10
model_params:
  temperature: 0.7
  max_tokens: 2048
---

You are a helpful AI assistant. You provide clear, concise, and accurate responses.
Be friendly but professional.
```

### Agent with Custom Tools

**AGENTS.md:**
```markdown
---
name: tool-agent
model: azure_ai/gpt-4o
extensions:
  - examples.custom_tools.tools
model_params:
  temperature: 0.1
  max_tokens: 2048
  seed: 0
---

You are an assistant with custom tools.
```

**tools.py:**
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

### Agent with Built-in Tools

**AGENTS.md:**
```markdown
---
name: dev-assistant
model: azure_ai/gpt-4o
permission:
  read: allow
  shell: allow
max_turns: 15
model_params:
  temperature: 0
  max_tokens: 4096
  seed: 0
---

You are a senior software engineer assistant. You help developers write,
review, and debug code.

You apply the skills injected below systematically when relevant.
```

**skills/code-review/SKILL.md:**
```markdown
---
name: code-review
description: Systematic checklist for reviewing code quality and correctness
---

When reviewing code, work through these categories in order:

1. **Correctness** -- Does the logic match the stated intent?
2. **Clarity** -- Are names descriptive?
3. **Error handling** -- Are errors caught at the right level?
4. **Performance** -- Any obvious O(n^2) loops?
5. **Security** -- Any injection risks?
6. **Tests** -- Does the change come with tests?
```

### Agent with Memory

```markdown
---
name: sage-historian
model: azure_ai/gpt-4o
memory:
  backend: sqlite
  path: memory.db
  embedding: azure_ai/text-embedding-3-large
max_turns: 10
---

You are a concise historian. Answer questions using only the provided context.
```

### Agent with MCP

```markdown
---
name: mcp-assistant
model: azure_ai/claude-sonnet-4-6
permission:
  read: allow
  shell: allow
model_params:
  temperature: 0.0
  max_tokens: 4096
  timeout: 45.0
mcp_servers:
  filesystem:
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
memory:
  backend: sqlite
  path: mcp_agent_memory.db
  embedding: azure_ai/text-embedding-3-large
max_turns: 10
---

You are an assistant that can interact with the filesystem via MCP.
```

### Agent with Permissions

```markdown
---
name: safe-reviewer
model: azure_ai/gpt-4o
description: A code reviewer with strict permission boundaries
permission:
  read: allow
  shell:
    "*": ask
    "git status": allow
    "git diff*": allow
    "git log*": allow
---

You are a safe code reviewer. You have read-only access to the filesystem
and git history. Shell access is restricted to git commands.
```

### Agent with Context Management

```markdown
---
name: safe-coder
model: azure_ai/kimi-k2.5
description: A coding assistant with permissions and token budget management
permission:
  read: allow
  edit: allow
  shell:
    "*": ask
    "git status": allow
    "git diff*": allow
    "git log*": allow
context:
  compaction_threshold: 0.8
  reserve_tokens: 8192
  prune_tool_outputs: true
  tool_output_max_chars: 4000
---

You are a coding assistant. Be thoughtful about file modifications.
```

### Orchestrator with Subagents

```markdown
---
name: orchestrator
model: azure_ai/gpt-4o
subagents:
  - research_agent
  - summarize_agent
model_params:
  temperature: 0.5
  timeout: 120.0
---

You are an orchestrator that coordinates research and summarization.
```

### Programmatic Construction

```python
import asyncio
from sage import Agent, tool, Orchestrator, Pipeline

@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

async def main():
    # Single agent
    calc = Agent(
        name="calc",
        model="gpt-4o",
        body="You are a calculator. Use the add tool.",
        tools=[add],
    )
    result = await calc.run("What is 17 + 25?")
    print(result)

    # Pipeline
    pipeline = Agent(name="a", model="gpt-4o", body="Expand") \
            >> Agent(name="b", model="gpt-4o", body="Summarize")
    result = await pipeline.run("Python decorators")

    # Parallel
    agents = [
        Agent(name="fast", model="gpt-4o-mini", body="Answer briefly"),
        Agent(name="deep", model="gpt-4o", body="Answer thoroughly"),
    ]
    results = await Orchestrator.run_parallel(agents, "Explain async/await")

    # Race
    winner = await Orchestrator.run_race(agents, "Quick answer needed")

    await calc.close()

asyncio.run(main())
```

---

## Public API (`sage/__init__.py`)

```python
from sage import (
    Agent,           # Core agent class
    tool,            # @tool decorator
    ToolBase,        # Stateful tool base class
    ToolRegistry,    # Tool dispatch
    LiteLLMProvider, # LLM provider
    Pipeline,        # Sequential orchestration
    Orchestrator,    # Parallel/race orchestration
    Message,         # Conversation message
    ToolCall,        # Tool invocation
    ToolSchema,      # Tool JSON schema
    CompletionResult,# Non-streaming result
    StreamChunk,     # Streaming chunk
    Usage,           # Token usage
    SageError,       # Base exception
    ConfigError,     # Config errors
    ProviderError,   # Provider errors
    ToolError,       # Tool errors
    SageMemoryError, # Memory errors
)
```

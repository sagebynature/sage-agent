# Sage Agent

Yes, I shamelessly named it after me ;)

Inspired by the recent sprawl of OpenClaw, PicoBot, ZeroClaw, and whatever else popped up last Tuesday — I decided to write my own. Written from the ground up in Python.

Sage doesn't aspire to be the next Claude Code. Instead, it's intentionally designed to be a **clean slate out of the box**, so that *you* can make it more intelligent. No opinions. No bloat. Just a solid foundation you can build on top of.

Built-in evaluation and CI/headless execution are included. See [`.docs/eval.md`](.docs/eval.md) and [`.docs/ci-headless.md`](.docs/ci-headless.md).

## Key Features

### Agents

The core unit. Define an agent in a Markdown file with YAML frontmatter — name, model, system prompt — and you're running. No boilerplate classes, no framework ceremony. Just config and go.

```markdown
---
name: assistant
model: gpt-4o
---
You are a helpful AI assistant.
```

### Subagents & Delegation

Agents can have subagents. When they do, they automatically get a `delegate` tool — the LLM decides when and how to hand off work. It's orchestration without the orchestration code.

### Tools via `@tool` Decorator

Write a Python function. Decorate it with `@tool`. Sage auto-generates the JSON schema from your type hints. That's it. No manual schema wrangling.

```python
@tool
def word_count(text: str) -> str:
    """Count the number of words in the given text."""
    return str(len(text.split()))
```

Built-in tools included — or load them all at once with `sage.tools.builtins`:

| Category | Tools |
|----------|-------|
| Core | `shell`, `file_read`, `file_write`, `file_edit`, `http_request` |
| Memory | `memory_store`, `memory_recall` |
| Web | `web_fetch`, `web_search` |
| Git | `git_status`, `git_diff`, `git_log`, `git_commit`, `git_undo`, `git_branch` |

### Skills

Reusable capabilities defined as Markdown files. Drop them in a `skills/` directory and all agents share them automatically. Sage resolves the global skill pool via a waterfall (`skills_dir` in `config.toml` → `./skills/` → `~/.agents/skills/` → `~/.claude/skills/`). Each agent can optionally limit its skills to a named subset via an allowlist in `config.toml`. Flat files or directory-per-skill — both work.

### Orchestration

Four flavors:

- **Pipeline** (`>>`) — chain agents sequentially. Output of one feeds the next.
- **Parallel** — run multiple agents concurrently via `Orchestrator.run_parallel()`.
- **Race** — first agent to complete wins via `Orchestrator.run_race()`.
- **Autonomous delegation** — an orchestrator agent with subagents decides who does what, on its own.

### 100+ LLM Providers

Powered by [litellm](https://github.com/BerriAI/litellm). OpenAI, Azure, Anthropic, Ollama, and basically everything else. One model string, any provider.

| Provider | Model String |
|----------|-------------|
| OpenAI | `gpt-4o`, `gpt-4o-mini` |
| Azure | `azure/gpt-4o` |
| Anthropic | `anthropic/claude-sonnet-4-20250514` |
| Ollama | `ollama/llama3` |

### MCP Support

Connect to MCP servers (stdio or SSE) or expose your tools *as* an MCP server. Both directions work.

### Semantic Memory

SQLite-backed with litellm embeddings. Zero-config persistent recall across sessions. Compaction built in so context doesn't bloat forever.

### Permissions

Control what tools can do via a single `permission:` block in YAML frontmatter. Each permission category (`read`, `edit`, `shell`, `web`, `memory`) maps to a set of built-in tools. Set a category to `allow`, `deny`, or `ask`, or use pattern matching for fine-grained shell control. When set to `deny`, tools are invisible to the LLM. Interactive prompts in the TUI when policy is `ask`.

### Hook System

A lifecycle event bus for intercepting and extending agent behavior without modifying core code. Register async handlers against named `HookEvent` values (`PRE_LLM_CALL`, `POST_LLM_CALL`, `POST_TOOL_EXECUTE`, `ON_DELEGATION`, `ON_COMPACTION`, …). Built-in hooks cover credential scrubbing, query-based model routing, bail-out retry (follow-through), and automatic memory injection. Hooks that raise never crash the agent — errors are logged and swallowed.

```python
from sage.hooks.registry import HookRegistry
from sage.hooks.base import HookEvent

hr = HookRegistry()

async def log_calls(event, data):
    print(f"{event}: {data.get('model')}")

hr.register(HookEvent.PRE_LLM_CALL, log_calls)
agent = Agent(name="a", model="gpt-4o", hook_registry=hr)
```

### Coordination

Agent-to-agent messaging and lifecycle primitives for multi-agent systems:

- **MessageBus** — in-memory per-agent inboxes with TTL expiry, idempotency, overflow protection, and broadcast delivery
- **CancellationScope** — propagate cancel signals across async tasks; child scopes inherit parent cancellation
- **SessionManager** — create, track, and destroy concurrent agent sessions with typed metadata

### Context Management

Token-aware context window management. Automatic compaction when approaching the model's limit — tries LLM summarization first, then emergency drop, then deterministic trim as a guaranteed last resort. Configurable reserve tokens and optional pruning of large tool outputs.

### TUI

A full interactive terminal UI built with [Textual](https://github.com/Textualize/textual). 80/20 split layout — chat panel on the left with markdown rendering, collapsible tool calls, and multiline input; status panel on the right with agent info and usage stats. Permission modals for interactive approval. Toggleable log panel (Ctrl+L).

```bash
sage tui --agent-config AGENTS.md
```

### Protocol-Based Architecture

`ProviderProtocol`, `MemoryProtocol`, `EmbeddingProtocol` — swap out any layer. Don't like the SQLite memory backend? Write your own. Don't want litellm? Implement the protocol. Everything is async-first.

## Quick Start

```bash
pip install sage-agent
# or
uv tool install sage-agent
```

```bash
export OPENAI_API_KEY=sk-...
sage agent run AGENTS.md --input "What is the capital of France?"
```

## Code API

```python
import asyncio
from sage import Agent

agent = Agent(
    name="assistant",
    model="gpt-4o",
    body="You are a helpful assistant.",
)

result = asyncio.run(agent.run("What is 2 + 2?"))
print(result)
```

Or load from config:

```python
agent = Agent.from_config("AGENTS.md")
result = asyncio.run(agent.run("Hello"))
```

### Pipelines

```python
pipeline = researcher >> summarizer
result = asyncio.run(pipeline.run("Explain quantum computing"))
```

### Parallel Execution

```python
from sage import Orchestrator

results = asyncio.run(Orchestrator.run_parallel(agents, "Analyze this topic"))
```

### Race Execution

```python
winner = asyncio.run(Orchestrator.run_race(agents, "Solve this problem"))
```

### Autonomous Orchestration

```markdown
---
name: orchestrator
model: gpt-4o
subagents:
  - research_agent
  - summarize_agent
---
You are an orchestrator. Use the delegate tool to assign tasks to your subagents.
```

```bash
sage agent run orchestrator/AGENTS.md --input "Research and summarize quantum computing"
```

## CLI

```bash
sage agent run AGENTS.md --input "Hello" [--stream]   # Run an agent
sage agent validate AGENTS.md                          # Validate config
sage agent list [directory]                            # List agent configs
sage agent orchestrate AGENTS.md --input "text"        # Run subagents in parallel
sage tool list AGENTS.md                               # List available tools
sage init [--name my-agent] [--model gpt-4o]           # Scaffold a new project
sage tui --agent-config AGENTS.md                      # Launch interactive TUI
sage exec AGENTS.md -i "Hello" [-o text|jsonl|quiet] [--timeout N] [--yes]    # Run headless (CI/scripting)
sage eval run suite.yaml [--min-pass-rate 0.9] [--runs N]                      # Run evaluation suite
sage eval validate suite.yaml                                                   # Validate suite file
sage eval history [--suite NAME] [--last N]                                     # Show run history
sage eval compare <run-id-1> <run-id-2>                                         # Compare two runs
sage eval list [directory]                                                       # Find suite files
```

## Configuration Reference

### Agent Config (Markdown Frontmatter)

```markdown
---
name: my-agent
model: gpt-4o
description: "A helpful assistant"   # Display only, NOT sent to model
max_turns: 10
max_depth: 3                       # Max delegation depth (default: 3)

git:
  auto_snapshot: true              # Auto-snapshot before edits (default: true)

# Tool access: permission categories drive tool registration
# Categories: read, edit, shell, web, memory, task, git
# Values: "allow" | "deny" | "ask" | {pattern: action, ...}
permission:
  read: allow
  edit: allow
  shell:
    "*": ask
    "git log*": allow
    "git diff*": allow
  web: allow

# Custom tool modules (in addition to permission-derived built-ins)
extensions:
  - myapp.tools                       # Your own tools (module path)

memory:
  backend: sqlite                    # "sqlite" (default) or "file"
  path: memory.db
  embedding: text-embedding-3-large
  compaction_threshold: 50
  auto_load: false                   # Auto-inject recalled memories pre-LLM-call
  auto_load_top_k: 5                 # How many memories to inject

subagents:
  - research_agent                   # Directory containing AGENTS.md
  - config: helper.md                # Reference another .md file
  - name: inline-helper              # Or define inline
    model: gpt-4o-mini

mcp_servers:
  filesystem:
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
  remote:
    transport: sse
    url: http://localhost:8080/sse


context:
  compaction_threshold: 0.75         # Compact at 75% of context window
  reserve_tokens: 4096
  prune_tool_outputs: true
  tool_output_max_chars: 5000

model_params:
  temperature: 0.7
  max_tokens: 2048

# Hook-driven features (all optional)
credential_scrubbing:
  enabled: true
  patterns: ["sk-.*", "Bearer .*"]
  allowlist: ["sk-test"]

query_classification:
  rules:
    - pattern: "python|code"
      model: gpt-4o
      priority: 1

follow_through:
  enabled: true
  patterns: ["I cannot", "I'm unable", "I don't have access"]

research:
  enabled: true
  max_sources: 3
  timeout: 10.0

session:
  enabled: true
---

You are a helpful AI assistant.
```

### Main Config (TOML)

Sage supports a global TOML config file for defaults and per-agent overrides. It's auto-discovered at `./config.toml` or `~/.config/sage/config.toml`, or set via `SAGE_CONFIG_PATH`.

```toml
# Optional: global skills directory (waterfall: $cwd/skills → ~/.agents/skills → ~/.claude/skills)
# skills_dir = "/path/to/skills"

# agents_dir = "agents/"   # default directory for agent discovery
# primary = "my-agent"     # default agent to run when none specified

[defaults]
model = "gpt-4o"
max_turns = 15

[agents.my-agent]
model = "gpt-4o-mini"
max_turns = 5
# Optional: limit this agent to a subset of the global skill pool
# skills = ["git-master", "terraform"]
```

Override priority: **main config defaults < per-agent overrides < frontmatter**.

## Architecture

```
sage/
  agent.py          # Core Agent class (run loop, delegation, hook emission)
  config.py         # Markdown frontmatter loading (Pydantic)
  models.py         # Message, ToolCall, ToolSchema, Usage, etc.
  exceptions.py     # SageError, ConfigError, ProviderError, ToolError
  frontmatter.py    # YAML frontmatter parser
  main_config.py    # TOML main config support
  research.py       # Pre-response research system
  providers/        # ProviderProtocol + LiteLLMProvider
  tools/            # @tool decorator, ToolRegistry, ToolDispatcher, builtins
  skills/           # Skill loader (markdown-based reusable capabilities)
  orchestrator/     # Orchestrator (parallel, race) + Pipeline (>>)
  memory/           # MemoryProtocol, SQLiteMemory, FileMemory, compaction
  hooks/            # HookRegistry, HookEvent, built-in hooks
  coordination/     # MessageBus, CancellationScope, SessionManager
  parsing/          # Multi-format tool call parser, JSON repair
  mcp/              # MCPClient + MCPServer
  permissions/      # PermissionProtocol, policy rules, interactive prompts
  context/          # Token-aware context budget, fallback table
  git/              # Git tools (status, diff, log, commit, undo, branch, worktree) + snapshot
  cli/              # Click CLI commands + Textual TUI
    main.py         # sage agent / exec / eval / tool / init / tui commands
    tui.py          # Textual interactive TUI
    exit_codes.py   # SageExitCode IntEnum (exit codes 0–7)
    output.py       # OutputWriter — TextWriter, JSONLWriter, QuietWriter
  eval/             # Built-in evaluation framework
    suite.py        # TestSuite, TestCase, EvalSettings, load_suite()
    assertions.py   # 11 assertion types + run_assertion()
    runner.py       # EvalRunner, CaseResult, EvalRunResult
    history.py      # EvalHistory — SQLite run history (~/.config/sage/eval_history.db)
    report.py       # Text/JSON/comparison formatters
```

## Examples

- [`examples/simple_agent/`](examples/simple_agent/) — Minimal agent with markdown config
- [`examples/custom_tools/`](examples/custom_tools/) — Agent with `@tool`-decorated functions
- [`examples/parallel_agents/`](examples/parallel_agents/) — Orchestrator with subagents
- [`examples/mcp_agent/`](examples/mcp_agent/) — Agent with MCP filesystem server
- [`examples/memory_agent/`](examples/memory_agent/) — Semantic memory backend usage
- [`examples/skills_agent/`](examples/skills_agent/) — Skills in action
- [`examples/skills_demo/`](examples/skills_demo/) — Complex skills demo
- [`examples/permissions_agent/`](examples/permissions_agent/) — Permission policies
- [`examples/safe_coder/`](examples/safe_coder/) — Code generation with safety
- [`examples/devtools_agent/`](examples/devtools_agent/) — Developer tools
- [`examples/claude_agent/`](examples/claude_agent/) — Anthropic Claude model

## Requirements

- Python 3.10+
- See `pyproject.toml` for full dependency list

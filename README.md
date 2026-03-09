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

The `delegate` tool accepts two optional parameters beyond the target agent and task:

- **`session_id`** — resume a previous conversation with the subagent. Conversation history is persisted across calls and restored automatically. The result is prefixed with `[Session: <id>]` when a session ID is supplied.
- **`category`** — route the delegation to a model defined in the `categories` block of `config.toml` (e.g. `"quick"` → `gpt-4o-mini`, `"deep"` → Claude Sonnet). The subagent's model is swapped at runtime without changing its config file.

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
| Memory | `memory_store`, `memory_recall`, `memory_forget`, `memory_add`, `memory_search`, `memory_get`, `memory_list`, `memory_delete`, `memory_stats` |
| Process | `process_start`, `process_send`, `process_read`, `process_wait`, `process_kill`, `process_list` |
| Web | `web_fetch`, `web_search` |
| Git | `git_status`, `git_diff`, `git_log`, `git_commit`, `git_undo`, `git_branch` |

Per-agent tool restrictions are supported via frontmatter. `blocked_tools` hides specific tools from the LLM; `allowed_tools` is an explicit allowlist (all others are hidden). Blocklist takes precedence over allowlist.

```markdown
---
blocked_tools: [shell, http_request]
allowed_tools: [file_read, file_write, memory_store]
---
```

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

Connect to MCP servers (stdio or SSE) or expose your tools *as* an MCP server. Server definitions live in `config.toml` under `[mcp_servers.<name>]`; agents opt into them with `enabled_mcp_servers` in frontmatter or per-agent TOML overrides. MCP tools are registered with server-aware runtime names like `mcp_context7_resolve-library-id`.

### Semantic Memory

SQLite-backed with litellm embeddings. Zero-config persistent recall across sessions. Compaction built in so context doesn't bloat forever.

### Permissions

Control what tools can do via a single `permission:` block in YAML frontmatter. Each permission category (`read`, `edit`, `shell`, `web`, `memory`, `process`, `task`, `git`) maps to a set of built-in tools. Set a category to `allow`, `deny`, or `ask`, or use pattern matching for fine-grained shell control. When set to `deny`, tools are invisible to the LLM. Interactive prompts in the TUI when policy is `ask`.

For trusted local runs, the CLI also supports `--yolo` / `-y` to bypass all permission checks entirely. This overrides both `ask` and explicit `deny` decisions for the current process, including `sage exec`, `sage agent run`, `sage agent orchestrate`, `sage serve`, and `sage-tui`.

### Hook System

A lifecycle event bus for intercepting and extending agent behavior without modifying core code. Register async handlers against named `HookEvent` values — 31 events across seven categories: run lifecycle (`ON_RUN_STARTED`, `ON_RUN_COMPLETED`, `ON_RUN_FAILED`, `ON_RUN_CANCELLED`), LLM calls (`PRE_LLM_CALL`, `POST_LLM_CALL`, `ON_LLM_STREAM_DELTA`, `ON_LLM_ERROR`, `ON_LLM_RETRY`), tools (`PRE_TOOL_EXECUTE`, `POST_TOOL_EXECUTE`, `ON_TOOL_FAILED`), delegation (`ON_DELEGATION`, `ON_DELEGATION_COMPLETE`, `ON_DELEGATION_FAILED`), memory, compaction, permissions, sessions, coordination, and planning. Built-in hooks cover credential scrubbing, query-based model routing, bail-out retry (follow-through), automatic memory injection, notepad injection, and plan analysis. Hooks that raise never crash the agent — errors are logged and swallowed.

```python
from sage.hooks.registry import HookRegistry
from sage.hooks.base import HookEvent

hr = HookRegistry()

async def log_calls(event, data):
    print(f"{event}: {data.get('model')}")

hr.register(HookEvent.PRE_LLM_CALL, log_calls)
agent = Agent(name="a", model="gpt-4o", hook_registry=hr)
```

Every hook emission is also recorded as a canonical `EventEnvelope` by the telemetry layer (`sage/telemetry.py`). Each event carries correlation IDs (`run_id`, `session_id`, `originating_session_id`), timing, token usage, and a sanitized payload. The TUI's event timeline and inspector consume these envelopes via JSON-RPC for real-time visibility into agent behavior. See [ADR-012](.docs/adrs/012-event-telemetry-and-observability.md).

### Coordination

Agent-to-agent messaging and lifecycle primitives for multi-agent systems:

- **MessageBus** — in-memory per-agent inboxes with TTL expiry, idempotency, overflow protection, and broadcast delivery
- **CancellationScope** — propagate cancel signals across async tasks; child scopes inherit parent cancellation
- **SessionManager** — create, track, and destroy concurrent agent sessions with typed metadata
- **BackgroundTaskManager** — launch subagent runs as non-blocking asyncio tasks. The orchestrator gets a `delegate_background` tool and receives completion notifications injected into the next turn's message stream. Supports polling (`background_status`) and cancellation (`background_cancel`).

```python
# Orchestrator gets these tools automatically when subagents are present:
# delegate_background(agent_name, task) → task_id
# background_status(task_id) → status + result
# background_cancel(task_id) → bool
```

### Context Management

Token-aware context window management. Automatic compaction when approaching the model's limit — tries LLM summarization first, then emergency drop, then deterministic trim as a guaranteed last resort. Configurable reserve tokens and optional pruning of large tool outputs.

### TUI

A full interactive terminal UI built with [Ink v6](https://github.com/vadimdemedes/ink) and React 19. Communicates with the Python backend via JSON-RPC over stdio. Block-based conversation display with live streaming, collapsible tool calls, markdown rendering, permission prompts, delegation hierarchy visualization, an active task dock, live turn complexity display, and an event timeline with inspector for real-time observability.

**Prerequisites:** Node.js 22+, pnpm 10+

```bash
# Install dependencies
make tui-install

# Build
make tui-build

# Install globally on PATH
make tui-install-global

# Development mode (hot reload)
make tui-dev
```

See [`tui/README.md`](tui/README.md) for slash commands, keyboard shortcuts, and architecture details.

### Planning Pipeline

A structured plan-then-execute loop for long-horizon tasks. Enable it via `planning:` in frontmatter.

- **`plan_create`** — agents call this tool to create a named plan with an ordered list of task descriptions. State persists to disk under `.sage/plans/`.
- **`plan_status` / `plan_update` / `plan_complete`** — query and mutate plan state across turns and sessions.
- **`notepad_write` / `notepad_read`** — persistent markdown working memory scoped to a plan. Notes are stored under `.sage/notepads/<plan_name>/` and injected automatically before each LLM call via the built-in notepad hook.
- **Plan analysis** — optional `ON_PLAN_CREATED` hook that makes an LLM call to identify ambiguities, missing dependencies, ordering issues, and risks in a newly created plan. Enable via `planning.analysis.enabled: true`.
- **Review loop** — `review_loop(plan, reviewer, reviser)` iterates through review-revise cycles using the `PlanReviewer` protocol. The shipped `LLMPlanReviewer` evaluates specificity, success criteria, and dependencies. Configurable via `planning.review`.
- **`ConductorMixin`** — mixin for orchestrator agents that drives plan execution: reads the plan, delegates each pending task to an `executor` subagent, and persists results after each step.

```markdown
---
name: planner
model: gpt-4o
planning:
  analysis:
    enabled: true
  review:
    enabled: true
    max_iterations: 3
---
You are a planning agent. Use plan_create to structure work, then execute step by step.
```

### Prompt System

**Model-specific overlays** — lightweight transformations applied to the assembled system prompt after all content (body, identity, skills) has been joined. Each overlay targets a model family and appends model-tuned instructions.

Built-in overlays:
- `GeminiOverlay` — appends a tool-call enforcement reminder for `gemini/*` models
- `GPTOverlay` — appends a "format reasoning in clear steps" hint for `gpt-*` models

Register custom overlays via `overlay_registry.register(my_overlay)` from `sage.prompts`.

**Dynamic delegation table** — orchestrator agents can include `{{DELEGATION_TABLE}}` in their system prompt body. Sage replaces this placeholder at runtime with a markdown table of all available subagents, derived from each agent's `prompt_metadata` frontmatter field.

```markdown
---
name: orchestrator
model: gpt-4o
subagents: [researcher, summarizer]
---
You are the orchestrator.

{{DELEGATION_TABLE}}

Use the delegate tool to assign work.
```

```markdown
# researcher/AGENTS.md
---
name: researcher
model: gpt-4o
description: "Finds primary sources and synthesizes citations"
prompt_metadata:
  cost: moderate
  use_when: ["deep research", "fact checking", "citations needed"]
  avoid_when: ["simple questions", "quick lookups"]
  triggers: ["research", "find sources", "citations"]
---
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
sage serve [--agent-config AGENTS.md]                  # Start JSON-RPC backend for the TUI
sage exec AGENTS.md -i "Hello" [-o text|jsonl|quiet] [--timeout N] [--yes|--yolo]  # Run headless
sage eval run suite.yaml [--min-pass-rate 0.9] [--runs N]                      # Run evaluation suite
sage eval validate suite.yaml                                                   # Validate suite file
sage eval history [--suite NAME] [--last N]                                     # Show run history
sage eval compare <run-id-1> <run-id-2>                                         # Compare two runs
sage eval list [directory]                                                       # Find suite files
```

YOLO mode examples:

```bash
sage --yolo agent run AGENTS.md -i "Refactor this project"
sage exec AGENTS.md -i "Run the migration" -y
sage serve --agent-config AGENTS.md --yolo
sage-tui --yolo
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
# Categories: read, edit, shell, web, memory, process, task, git
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

enabled_mcp_servers: [filesystem, remote]


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

# Per-agent tool restrictions
blocked_tools: [shell, http_request]   # always hidden from the LLM
# allowed_tools: [file_read, memory_store]  # allowlist (all others hidden)

# Planning pipeline (Phase 3)
planning:
  analysis:
    enabled: true                      # Analyze new plans for gaps/risks
    prompt: "custom prompt (optional)" # Override DEFAULT_ANALYSIS_PROMPT
  review:
    enabled: true
    max_iterations: 3
    prompt: "custom review prompt"     # Override DEFAULT_REVIEW_PROMPT

# Dynamic prompt metadata (used by {{DELEGATION_TABLE}} in orchestrators)
prompt_metadata:
  cost: cheap                          # free | cheap | moderate | expensive
  triggers: ["research", "summarize"]
  use_when: ["deep research needed"]
  avoid_when: ["simple questions"]
---

You are a helpful AI assistant.
```

### Main Config (TOML)

Sage supports a global TOML config file for top-level defaults and per-agent overrides. It's auto-discovered at `./config.toml` or `~/.config/sage/config.toml`, or set via `SAGE_CONFIG_PATH`.

```toml
# Optional: global skills directory (waterfall: $cwd/skills → ~/.agents/skills → ~/.claude/skills)
# skills_dir = "/path/to/skills"

# agents_dir = "agents/"   # default directory for agent discovery
# primary = "my-agent"     # default agent to run when none specified

model = "gpt-4o"
max_turns = 15
enabled_mcp_servers = ["context7"]

[complexity]
enabled = true
simple_threshold = 100
complex_threshold = 500

[mcp_servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp@latest"]

[agents.my-agent]
model = "gpt-4o-mini"
max_turns = 5
enabled_mcp_servers = ["context7"]
# Optional: limit this agent to a subset of the global skill pool
# skills = ["git-master", "terraform"]

# Category-based model routing — used by the `category` parameter on `delegate`
[categories.quick]
model = "gpt-4o-mini"

[categories.deep]
model = "anthropic/claude-sonnet-4-20250514"

[categories.deep.model_params]
temperature = 0.2
```

Override priority: **top-level main config < per-agent overrides < frontmatter**.

## Architecture

```
sage/
  agent.py          # Core Agent class (run loop, delegation, hook emission)
  config.py         # Markdown frontmatter loading (Pydantic)
  models.py         # Message, ToolCall, ToolSchema, Usage, etc.
  events.py         # Typed event dataclasses (ToolStarted, LLMTurnCompleted, …)
  telemetry.py      # EventEnvelope, TelemetryRecorder, ExecutionContext, sanitization
  tracing.py        # OpenTelemetry span() wrapper (real spans or no-op)
  exceptions.py     # SageError, ConfigError, ProviderError, ToolError
  frontmatter.py    # YAML frontmatter parser
  main_config.py    # TOML main config support (categories, per-agent overrides)
  research.py       # Pre-response research system
  providers/        # ProviderProtocol + LiteLLMProvider
  tools/            # @tool decorator, ToolRegistry (allowlist/blocklist), builtins
  skills/           # Skill loader (markdown-based reusable capabilities)
  orchestrator/     # Orchestrator (parallel, race) + Pipeline (>>)
  memory/           # MemoryProtocol, SQLiteMemory, FileMemory, compaction
  hooks/            # HookRegistry, HookEvent (31 events), built-in hooks
                    #   builtin/notepad_injector.py  — injects notepad before LLM call
                    #   builtin/plan_analyzer.py     — ON_PLAN_CREATED analysis hook
  coordination/     # MessageBus, CancellationScope, SessionManager
                    #   background.py  — BackgroundTaskManager + BackgroundTaskInfo
  planning/         # Planning pipeline
                    #   state.py     — PlanState, PlanStateManager, PlanTask
                    #   notepad.py   — Notepad (persistent markdown working memory)
                    #   review.py    — PlanReviewer protocol, LLMPlanReviewer, review_loop()
                    #   conductor.py — ConductorMixin (plan-driven orchestration)
  prompts/          # Prompt construction utilities
                    #   overlays.py        — PromptOverlay protocol, OverlayRegistry, built-ins
                    #   dynamic_builder.py — build_delegation_table(), build_orchestrator_prompt()
  parsing/          # Multi-format tool call parser, JSON repair
  protocol/         # JSON-RPC bridge to TUI (EventBridge, session, notifications)
  mcp/              # MCPClient + MCPServer
  permissions/      # PermissionProtocol, policy rules, interactive prompts
  context/          # Token-aware context budget, fallback table
  git/              # Git tools (status, diff, log, commit, undo, branch, worktree) + snapshot
  cli/              # Click CLI commands
    main.py         # sage agent / exec / eval / tool / init / serve commands
    exit_codes.py   # SageExitCode IntEnum (exit codes 0–7)
    output.py       # OutputWriter — TextWriter, JSONLWriter, QuietWriter
  eval/             # Built-in evaluation framework
    suite.py        # TestSuite, TestCase, EvalSettings, load_suite()
    assertions.py   # 11 assertion types + run_assertion()
    runner.py       # EvalRunner, CaseResult, EvalRunResult
    history.py      # EvalHistory — SQLite run history (~/.config/sage/eval_history.db)
    report.py       # Text/JSON/comparison formatters

tui/                # TypeScript terminal UI (Ink v6 + React 19)
  src/
    components/     # ConversationView, ActiveStreamView, EventTimeline, EventInspector, …
    integration/    # EventNormalizer, EventProjector, BlockEventRouter, LifecycleManager
    state/          # BlockContext + blockReducer (block-based state management)
    ipc/            # SageClient (JSON-RPC over stdio)
    renderer/       # Markdown + syntax-highlighted code blocks
    commands/       # Slash command registry (24 commands)
```

## Examples

- [`examples/simple-assistant.md`](examples/simple-assistant.md) — Minimal single-agent config
- [`examples/custom_tools/`](examples/custom_tools/) — Agent with `@tool`-decorated functions
- [`examples/parallel_agents/`](examples/parallel_agents/) — Orchestrator with subagents
- [`examples/mcp-assistant.md`](examples/mcp-assistant.md) — Agent that opts into centrally configured MCP servers
- [`examples/memory_agent/`](examples/memory_agent/) — Semantic memory backend usage
- [`examples/skills_agent/`](examples/skills_agent/) — Skills in action
- [`examples/skills_demo/`](examples/skills_demo/) — Demo-local skills bundle
- [`examples/category_routing_with_tool_restrictions/`](examples/category_routing_with_tool_restrictions/) — Category routing plus permission/tool controls
- [`examples/safe_coder/`](examples/safe_coder/) — Code generation with safety
- [`examples/devtools.md`](examples/devtools.md) — Developer tools agent
- [`examples/orchestrated_agents/`](examples/orchestrated_agents/) — Conductor/planner/executor pattern with planning pipeline

## Requirements

- Python 3.10+
- See `pyproject.toml` for full dependency list

### TUI (optional)

- Node.js 22+
- pnpm 10+
- See `tui/package.json` for full dependency list

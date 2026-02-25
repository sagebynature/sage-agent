# Sage

Yes, I shamelessly named it after me ;)

Inspired by the recent sprawl of OpenClaw, PicoBot, ZeroClaw, and whatever else popped up last Tuesday — I decided to write my own. Written from the ground up in Python.

Sage doesn't aspire to be the next Claude Code. Instead, it's intentionally designed to be a **clean slate out of the box**, so that *you* can make it more intelligent. No opinions. No bloat. Just a solid foundation you can build on top of.

## Key Features

### 🤖 Agents

The core unit. Define an agent in a Markdown file with YAML frontmatter — name, model, system prompt — and you're running. No boilerplate classes, no framework ceremony. Just config and go.

```markdown
---
name: assistant
model: gpt-4o
---
You are a helpful AI assistant.
```

### 🧠 Subagents & Delegation

Agents can have subagents. When they do, they automatically get a `delegate` tool — the LLM decides when and how to hand off work. It's orchestration without the orchestration code.

### 🔧 Tools via `@tool` Decorator

Write a Python function. Decorate it with `@tool`. Sage auto-generates the JSON schema from your type hints. That's it. No manual schema wrangling.

```python
@tool
def word_count(text: str) -> str:
    """Count the number of words in the given text."""
    return str(len(text.split()))
```

Built-in tools included: `shell`, `file_read`, `file_write`, `http_request`, `memory_store`, `memory_recall` — or load them all at once with `sage.tools.builtins`.

### 📚 Skills

Reusable capabilities defined as Markdown files. Drop them in a directory, and agents can load them. Flat files or directory-per-skill — both work. Skills are just knowledge and instructions, cleanly separated from tools.

### ⚡ Orchestration

Three flavors:

- **Pipeline** (`>>`) — chain agents sequentially. Output of one feeds the next.
- **Parallel** — run multiple agents concurrently via `Orchestrator.run_parallel()`.
- **Autonomous delegation** — an orchestrator agent with subagents decides who does what, on its own.

### 🔌 100+ LLM Providers

Powered by [litellm](https://github.com/BerriAI/litellm). OpenAI, Azure, Anthropic, Ollama, and basically everything else. One model string, any provider.

| Provider | Model String |
|----------|-------------|
| OpenAI | `gpt-4o`, `gpt-4o-mini` |
| Azure | `azure/gpt-4o` |
| Anthropic | `anthropic/claude-sonnet-4-20250514` |
| Ollama | `ollama/llama3` |

### 🧩 MCP Support

Connect to MCP servers (stdio or SSE) or expose your tools *as* an MCP server. Both directions work.

### 💾 Semantic Memory

SQLite-backed with litellm embeddings. Zero-config persistent recall across sessions. Compaction built in so context doesn't bloat forever.

### 🖥️ TUI

A full interactive terminal UI built with [Textual](https://github.com/Textualize/textual). Split-screen layout — chat on the left, live tool-call feed on the right, status bar at the bottom. It's actually nice to use.

### 🏗️ Protocol-Based Architecture

`ProviderProtocol`, `MemoryProtocol`, `EmbeddingProtocol` — swap out any layer. Don't like the SQLite memory backend? Write your own. Don't want litellm? Implement the protocol. Everything is async-first.

## Quick Start

```bash
pip install sage
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
sage tool list AGENTS.md                               # List available tools
sage init [--name my-agent] [--model gpt-4o]           # Scaffold a new project
```

## Configuration Reference

```markdown
---
name: my-agent
model: gpt-4o
description: "A helpful assistant"   # Display only, NOT sent to model
max_turns: 10

tools:
  - shell
  - file_read
  - file_write
  - http_request
  - memory_store
  - memory_recall
  - sage.tools.builtins              # All built-in tools at once
  - myapp.tools:search               # Your own tools (module:name)

memory:
  backend: sqlite
  path: memory.db
  embedding: text-embedding-3-large
  compaction_threshold: 50

subagents:
  - research_agent                   # Directory containing AGENTS.md
  - config: helper.md                # Reference another .md file
  - name: inline-helper              # Or define inline
    model: gpt-4o-mini

mcp_servers:
  - transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
  - transport: sse
    url: http://localhost:8080/sse

model_params:
  temperature: 0.7
  max_tokens: 2048
---

You are a helpful AI assistant.
```

## Architecture

```
sage/
  agent.py          # Core Agent class (run loop, delegation)
  config.py         # Markdown frontmatter loading (Pydantic)
  models.py         # Message, ToolCall, ToolSchema, etc.
  providers/        # ProviderProtocol + LiteLLMProvider
  tools/            # @tool decorator, ToolRegistry, builtins
  skills/           # Skill loader (markdown-based reusable capabilities)
  orchestrator/     # Orchestrator (parallel) + Pipeline (>>)
  memory/           # MemoryProtocol, SQLiteMemory, embeddings, compaction
  mcp/              # MCPClient + MCPServer
  cli/              # Click CLI + Textual TUI
```

## Examples

- [`examples/simple_agent/`](examples/simple_agent/) — Minimal agent with markdown config
- [`examples/custom_tools/`](examples/custom_tools/) — Agent with `@tool`-decorated functions
- [`examples/parallel_agents/`](examples/parallel_agents/) — Orchestrator with subagents
- [`examples/mcp_agent/`](examples/mcp_agent/) — Agent with MCP filesystem server

## Requirements

- Python 3.11+
- See `pyproject.toml` for full dependency list

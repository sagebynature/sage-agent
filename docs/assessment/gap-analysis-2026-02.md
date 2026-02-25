# Sage V2 — Critical Assessment & Gap Analysis

**Date:** 2026-02-24
**Compared Against:** Claude Code (Anthropic), OpenCode (Anomaly Innovations)

---

## What Sage V2 Does Well

The SDK has solid engineering fundamentals: protocol-based extensibility, 281 tests with strict mypy, 10 ADRs documenting decisions, and a clean separation of concerns. The markdown-config-first design (AGENTS.md) is genuinely elegant — a single file defines both the system prompt and agent metadata. The `@tool` decorator with automatic JSON Schema generation from Python type hints is ergonomic. And the hybrid config + code API means simple agents need zero Python while complex ones get full programmatic control.

---

## Gap Analysis Against Claude Code and OpenCode

### 1. Tool System — Primitive

**Sage:** 6 built-in tools (`shell`, `file_read`, `file_write`, `http_request`, `memory_store`, `memory_recall`). Shell has basic deny-list safety (blocks `rm -rf /`).

**Claude Code:** ~15+ specialized tools including `Read` (with line ranges, image support, PDF, Jupyter), `Edit` (exact string replacement with uniqueness enforcement), `Glob`, `Grep` (ripgrep-backed with regex, context lines, multiline), `WebSearch`, `WebFetch`, `NotebookEdit`, and granular file operations that never shell out unnecessarily.

**OpenCode:** Similar tool depth — `read`, `write`, `edit`, `bash`, `glob`, `grep`, `list`, `patch`, `lsp`, `todo`, `task`, `skill`, `webfetch`, `websearch`, `codesearch`. The `lsp` tool provides code intelligence (go-to-definition, references, call hierarchy).

**Gap:** Sage's `file_read`/`file_write` and `shell` are blunt instruments. No `edit` tool for surgical string replacement (agents must rewrite entire files). No `glob`/`grep` equivalents — the agent must use `shell` with `find`/`grep`, which is error-prone and wastes tokens. No web search, no code search, no LSP integration, no notebook support.

**Priority: High.** Tools are the agent's hands. Weak tools mean weak agents regardless of how good the orchestration is.

---

### 2. Permission & Safety Model — Missing

**Sage:** A hardcoded deny-list in `shell()` blocking 6 patterns (`rm -rf /`, `mkfs`, etc.). No permission framework.

**Claude Code:** Granular permission modes (`acceptEdits`, `plan`, `bypassPermissions`), tool-level approval, sandbox execution, and user consent flows.

**OpenCode:** Pattern-based permission rules per tool (`"bash": {"git *": "allow", "rm *": "deny", "*": "ask"}`), per-agent permission overrides, and an `ask` mode that prompts the user.

**Gap:** Sage has no user-consent mechanism, no sandboxing, no per-tool permission policies. Any agent with `shell` access can run arbitrary commands with no guardrails beyond the trivial deny-list. This is a serious blocker for production use.

**Priority: Critical** for any real-world deployment.

---

### 3. Context Management & Compaction — Rudimentary

**Sage:** Memory compaction via LLM summarization when message count exceeds a threshold. Semantic recall (SQLite + cosine similarity) before first LLM call.

**Claude Code:** Automatic summarization with unlimited context through sliding windows. Conversation history persists seamlessly.

**OpenCode:** Compaction at 75% context window usage, pruning of old tool outputs, provider-specific prompt caching, and a plugin hook (`session.compacting`) that lets plugins inject context to survive compaction. Community plugins (supermemory, mem, agent-memory) address the context loss problem.

**Gap:** Sage's compaction is count-based rather than token-based — it doesn't account for actual context window utilization. No prompt caching support. No mechanism to preserve critical context through compaction. No plugin hook to let extensions influence what survives summarization.

**Priority: High.** Context management directly determines how long and complex an agent session can be.

---

### 4. Multi-Agent Architecture — Basic

**Sage:** `Orchestrator.run_parallel()`, `run_race()`, `Pipeline`, and an auto-generated `delegate` tool. The LLM decides when to delegate. No inter-agent messaging, no shared state, no event system.

**Claude Code:** Team creation with named agents, inter-agent messaging (`SendMessage`), task lists (`TaskCreate`/`TaskUpdate`/`TaskList`), broadcast, shutdown protocols, peer-to-peer DMs, and automatic idle management.

**OpenCode:** Event-driven teams with peer-to-peer messaging, multi-model support within a team, single-process architecture with clean state tracking. Each subagent gets its own context window and can use a different LLM.

**Gap:** Sage's orchestration is fire-and-forget. No communication channel between running agents. No shared task tracking. No ability to mix models across agents in a team. The `delegate` tool is a simple call-and-return — no ongoing collaboration.

**Priority: Medium-High.** Multi-agent is increasingly table-stakes for complex tasks.

---

### 5. Plugin/Extension Ecosystem — Nascent

**Sage:** Skills loaded from `.md` files, appended to system prompt. No event system, no plugin hooks, no package-based extensions.

**OpenCode:** 20+ event hooks (`file.edited`, `session.compacted`, `permission.asked`, etc.), npm-based plugin distribution with auto-install, and a community ecosystem of 60+ plugins. Plugins can override tools, inject compaction context, and hook into the full session lifecycle.

**Gap:** Sage skills are static prompt injections — they can't react to events, modify behavior, or extend functionality. No hook system means no third-party extensibility beyond writing custom tools.

**Priority: Medium.** Important for ecosystem growth but not blocking for core functionality.

---

### 6. Configuration Layering — Flat

**Sage:** Single config file (AGENTS.md) with no inheritance or layering.

**OpenCode:** 4-layer config hierarchy: remote org defaults -> global user config -> custom env overrides -> project config. JSON Schema validation. Variable substitution with `{env:VARIABLE_NAME}`.

**Claude Code:** Project-level CLAUDE.md, user-level global instructions, team-level settings.

**Gap:** No way to set organization defaults, no global user preferences that apply across projects, no environment variable substitution in config. Every agent config is standalone.

**Priority: Medium.** Matters for enterprise adoption.

---

### 7. Developer Experience — Functional but Sparse

**Sage TUI:** Textual-based with chat panel + tool activity panel. Monkey-patches `ToolRegistry.execute()` for event emission (fragile).

**Claude Code:** Rich terminal UX with permission dialogs, progress indicators, syntax-highlighted diffs, inline file references, background task management, and deep IDE integration (VS Code, JetBrains).

**OpenCode:** SolidJS + Zig-backed TUI with optimized rendering, input attachments (files, symbols), bash mode prefix, session navigation between parent/child agents, and `/connect` for interactive key setup.

**Gap:** No IDE integration. No diff preview before file writes. No syntax highlighting in output. No session persistence across runs. No interactive permission dialogs. The monkey-patching approach for TUI events is a code smell.

**Priority: Medium.** UX determines adoption velocity.

---

### 8. Observability & Debugging — Logging Only

**Sage:** Python `logging` module with per-module loggers. Structured-ish (tool names, argument counts in log messages). No tracing, no token budget tracking, no cost estimation.

**Claude Code/OpenCode:** Token usage tracking per turn, cost estimation, session replay, and integration with external observability tools.

**Gap:** No token/cost tracking visible to users. No way to replay or inspect past sessions. No structured telemetry for production monitoring. The `Usage` model exists in code but isn't surfaced to users.

**Priority: Medium.** Critical for production but less so for an SDK.

---

### 9. Version Control Integration — Absent

**Claude Code:** Deep git integration with commit creation, PR workflows, diff analysis, branch management, and safety protocols (never force-push, never amend without asking).

**OpenCode:** Internal git-based snapshot/undo system. Every file operation is tracked, enabling rollback of AI-made changes. GitHub Actions integration for autonomous PR creation.

**Gap:** Sage has no git awareness whatsoever. No snapshot/undo, no PR creation, no diff preview. An agent can accidentally destroy a codebase with `shell("rm -rf .")` and there's no recovery mechanism.

**Priority: High** for coding agent use cases.

---

### 10. LSP / Code Intelligence — Absent

**OpenCode:** Experimental LSP integration providing go-to-definition, find-references, hover info, and call hierarchy. Connects to language servers for Rust, TypeScript, Python, Swift, Terraform, etc.

**Claude Code:** No native LSP but compensates with powerful grep/glob tools and deep codebase exploration patterns.

**Gap:** Sage has neither LSP nor powerful search tools. Agents navigate code exclusively through `file_read` and `shell`, which is slow and token-expensive.

**Priority: Medium.** High impact for code-heavy use cases.

---

## Priority Roadmap

| Priority | Gap | Impact |
|----------|-----|--------|
| **Critical** | Permission & safety model | Blocks production use |
| **High** | Rich tool set (edit, glob, grep, web) | Directly limits agent capability |
| **High** | Git integration & undo/snapshots | Safety net for destructive operations |
| **High** | Token-aware context management | Limits session length and complexity |
| **Medium-High** | Inter-agent communication & task tracking | Required for complex multi-agent workflows |
| **Medium** | Plugin/event hook system | Ecosystem and extensibility |
| **Medium** | Config layering & env substitution | Enterprise adoption |
| **Medium** | Observability (token tracking, cost, replay) | Production monitoring |
| **Medium** | IDE integration | Developer adoption |
| **Medium** | LSP / code intelligence | Code-heavy use cases |

---

## Strategic Positioning

The markdown-config-first design and Python-native approach are genuine differentiators. Rather than trying to replicate Claude Code or OpenCode feature-for-feature, Sage could carve a niche as:

### 1. The Python-Native Agent SDK
OpenCode is TypeScript, Claude Code is closed-source. Python dominates ML/AI tooling. Lean into the ecosystem (Jupyter, pandas, scikit-learn, LangChain interop).

### 2. Embeddable Agent Runtime
Claude Code and OpenCode are standalone products. Sage could focus on being embedded into larger Python applications (`agent = Agent.from_config("agents.md"); result = await agent.run(input)`). The programmatic API is already there — make it the primary value proposition.

### 3. Protocol Extensibility
The `ProviderProtocol`, `MemoryProtocol`, `EmbeddingProtocol` pattern is clean. Expand this to `PermissionProtocol`, `ObservabilityProtocol`, `StorageProtocol` etc., making every concern pluggable.

### Risk
Trying to be a general-purpose coding agent competitor to tools with 110K+ stars and millions of users.

### Opportunity
Being the best way to build and ship custom AI agents in Python applications.

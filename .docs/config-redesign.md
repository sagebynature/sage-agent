# Agent Configuration Redesign: Research & Assessment

> Generated 2026-02-28 from competitive analysis against agent-zero, zeroclaw, nullclaw, openclaw, and AIEOS v1.2 spec.

---

## Table of Contents

1. [Design Proposal](#design-proposal)
2. [AIEOS v1.2 Analysis](#aieos-v12-analysis)
3. [Framework Comparisons](#framework-comparisons)
4. [Assessment Matrix](#assessment-matrix)
5. [Critical Finding: AIEOS Is Identity, Not Runtime](#critical-finding-aieos-is-identity-not-runtime)
6. [Orchestration Analysis](#orchestration-analysis)
7. [Recommended Architecture](#recommended-architecture)
8. [Implementation Decisions](#implementation-decisions)

---

## Design Proposal

Redesign how sage-agent is configured and how agents are composed.

**5 proposed design points:**

1. Each agent is defined by the AIEOS spec (https://aieos.org/)
2. sage-agent has 1 primary agent
3. sage-agent can optionally define secondary agents
4. Each agent is referenced by filename from a base `agent_path`
5. `agent_path` is specified in `config.toml`; defaults to `agents/` from CWD

---

## AIEOS v1.2 Analysis

**Source:** `https://aieos.org/schema/v1.2/aieos.schema.json` (GitHub: `entitai/aieos`)

AIEOS v1.2 is an **identity and persona specification**, not a runtime agent configuration spec. This is the single most critical finding from the research.

### Schema Top-Level Sections

| Section | Purpose | Fields |
|---------|---------|--------|
| `standard` | Protocol version | `"AIEOS"`, `"1.2.0"` |
| `metadata` | Entity identity | `entity_id` (UUID v4), Ed25519 keypair (`public_key`, `signature`), `alias`, versioning |
| `presence` | Network endpoints | IPv4/IPv6/webhook, social handles, settlement wallets for payments |
| `capabilities` | Declarative skill discovery | `skills[]` with `{ name, description, uri, version, auto_activate, priority(1-10) }` |
| `identity` | Names and biography | Names, bio, origin, residence |
| `physicality` | Avatar generation | Face/body/style descriptors |
| `psychology` | Behavioral model | `neural_matrix` (creativity/empathy/logic/adaptability/charisma/reliability as 0.0-1.0), OCEAN traits, MBTI, moral compass, emotional profile |
| `linguistics` | Communication style | TTS config, `text_style` (formality/verbosity), syntax preferences, `idiolect` (catchphrases, forbidden words) |
| `history` | Background story | Origin story, education, occupation, key life events |
| `motivations` | Goals and drives | Core drive, goals (short/long term), fears |

### What AIEOS Does NOT Have

- Model / provider configuration (which LLM to use)
- Temperature, max_tokens, top_p, or any inference parameters
- Tool definitions or allowed tools
- System prompts or prompt templates
- Parent/child relationships or orchestration semantics
- `agent_path`, `max_depth`, `max_iterations`
- Sandbox or security configuration
- Permission models

### Industry Adoption Pattern

- **zeroclaw** — supports AIEOS as an optional identity FORMAT (`[identity] format = "aieos"`) alongside native config
- **nullclaw** — supports AIEOS as an optional identity FORMAT (`format: "aieos"`) alongside native config
- **openclaw** — supports AIEOS via `identity?: IdentityConfig` alongside native config
- **PicoClaw** (14K stars) — has an open issue to integrate AIEOS similarly
- **No framework uses AIEOS as the complete agent definition**

---

## Framework Comparisons

### agent-zero (Python)

**Source:** https://github.com/agent0ai/agent-zero

**Agent profiles** are named directories under `agents/`:

```
agents/
├── default/
│   ├── agent.json        # { title, description, context }
│   └── prompts/          # optional markdown override files
├── developer/
│   └── agent.json
└── researcher/
    └── agent.json
```

**Key patterns:**

- **Profile slug = directory name** = agent reference (this is the `agent_path` equivalent)
- **4-tier resolution**: project `.a0proj/agents/<profile>/` → project root → `usr/agents/<profile>/` → built-in `agents/<profile>/`
- **`AgentConfig` dataclass**: `chat_model`, `utility_model`, `embeddings_model`, `browser_model`, `mcp_servers`, `profile` (slug), `memory_subdir`, `knowledge_subdirs`
- **Per-profile settings**: `settings.json` inside profile dir overrides model/MCP config
- **Orchestration**: Linear superior→subordinate chain via `call_subordinate` tool. LLM selects profile slug at delegation time. Agent numbering by depth (`self.agent.number + 1`). Shared `AgentContext`, isolated history per agent.
- **Extension system**: Numbered Python files in `extensions/<hook>/` directories, executed in order

### zeroclaw (Rust, 21.1K stars)

**Source:** https://github.com/zeroclaw-labs/zeroclaw

**Config format:** TOML at `~/.zeroclaw/config.toml`

**Resolution:** `ZEROCLAW_WORKSPACE` env → `active_workspace.toml` → `~/.zeroclaw/config.toml`

**Primary agent:** Top-level `default_provider`, `default_model`, `default_temperature`

**Sub-agents:** `[agents]` HashMap of `DelegateAgentConfig`:

```rust
pub struct DelegateAgentConfig {
    pub provider: String,
    pub model: String,
    pub system_prompt: Option<String>,
    pub api_key: Option<String>,
    pub temperature: Option<f64>,
    pub max_depth: u32,          // default 3
    pub agentic: bool,
    pub allowed_tools: Vec<String>,
    pub max_iterations: usize,   // default 10
}
```

**Orchestration:**
- `delegate` tool — sync/blocking delegation to named sub-agent
- `subagent_spawn` — async/background spawn, returns `session_id`
- `[coordination]` section with `lead_agent`, typed message bus
- Cross-process agent discovery via shared SQLite at `~/.zeroclaw/agents.db`

**Identity:** `[identity]` section supports format `"openclaw"` or `"aieos"`

### nullclaw (Zig)

**Source:** https://github.com/nullclaw/nullclaw

**Config format:** JSON at `~/.nullclaw/config.json` (OpenClaw-compatible)

**Agent list:** `agents.list[{ id, model.primary, system_prompt }]` with `agents.defaults.model.primary`

**Named agent struct:**

```zig
NamedAgentConfig {
    name: []const u8,
    provider: []const u8,
    model: []const u8,
    system_prompt: ?[]const u8,
    api_key: ?[]const u8,
    temperature: ?f64,
    max_depth: u32 = 3,
}
```

**Orchestration:**
- OS threads via `std.Thread.spawn` (2MB stack)
- Restricted tool set (no recursion)
- Results via event bus

**Runtime extras:** `exec_host` (sandbox/gateway/node), `exec_security` (deny/allowlist/full), `queue_mode`, memory profiles

**Identity:** Supports format `"nullclaw"`, `"openclaw"`, or `"aieos"`

### openclaw (TypeScript/Node.js)

**Source:** https://github.com/openclaw/openclaw

**Config format:** JSON5 at `~/.openclaw/openclaw.json`

**Agent type** (from `src/config/types.agents.ts`):

```typescript
type AgentConfig = {
    id: string;
    default?: boolean;
    name?: string;
    workspace?: string;
    agentDir?: string;
    model?: AgentModelConfig;
    skills?: string[];
    identity?: IdentityConfig;
    subagents?: { allowAgents?: string[]; model?: AgentModelConfig };
    sandbox?: AgentSandboxConfig;
    tools?: AgentToolsConfig;
    // ... plus memorySearch, humanDelay, heartbeat, groupChat, params
};
```

**Routing:** `AgentBinding` maps channel/account/peer to `agentId`; `BroadcastSchema` supports parallel/sequential multi-agent dispatch

**Workspace:** `~/.openclaw/workspace`; skills at `~/.openclaw/workspace/skills/<skill>/SKILL.md`

---

## Assessment Matrix

| # | Proposal | Verdict | Evidence |
|---|----------|---------|----------|
| 1 | Each agent defined by AIEOS | ⚠️ **Partially valid** — AIEOS covers identity only. All comparables separate identity from runtime config. | AIEOS schema lacks model, provider, tools, prompts, temperature, max_depth. zeroclaw/nullclaw/openclaw all treat AIEOS as an optional identity format, not the complete agent definition. |
| 2 | 1 primary agent | ✅ **Validated** | agent-zero: Agent 0; zeroclaw: top-level defaults; nullclaw: `agents.defaults`; openclaw: `default: true` flag |
| 3 | Optional secondary agents | ✅ **Validated** | zeroclaw: `[agents]` HashMap; nullclaw: `agents.list[]`; openclaw: agent list with bindings; agent-zero: named directory profiles |
| 4 | Referenced by filename from `agent_path` | ✅ **Validated** | agent-zero: `agents/<slug>/agent.json`; others use string keys/IDs but file-based approach is proven |
| 5 | `agent_path` in config.toml, default `agents/` from CWD | ✅ **Reasonable** | agent-zero has 4-tier resolution (project → user → default); zeroclaw uses workspace env → marker → home. Single path is sufficient for now. |

---

## Critical Finding: AIEOS Is Identity, Not Runtime

**AIEOS as the COMPLETE agent definition is not validated by any comparable.**

All frameworks that support AIEOS treat it as an optional identity layer, alongside separate runtime configuration for model, provider, tools, and orchestration.

**Recommendation:** Use AIEOS as an optional identity layer. Pair with sage-agent's existing runtime config (Markdown frontmatter + TOML).

---

## Orchestration Analysis

### sage-agent's Current Model

sage-agent already has **four orchestration modes**:

| Mode | Mechanism | Implementation |
|------|-----------|---------------|
| **Autonomous delegation** | `delegate` tool (sync) | `agent.py:_register_delegation_tools()` → creates `delegate(agent_name, task)` tool → LLM decides when/who → `await subagent.run(task)` → result as tool output |
| **Pipeline** | `>>` operator | `orchestrator/pipeline.py` — sequential, output feeds next |
| **Parallel** | `Orchestrator.run_parallel()` | `orchestrator/parallel.py` — `asyncio.gather`, all results collected |
| **Race** | `Orchestrator.run_race()` | `orchestrator/parallel.py` — `asyncio.as_completed`, first success wins |

### Comparison with Frameworks

| Capability | sage-agent | zeroclaw | nullclaw | agent-zero |
|------------|-----------|----------|----------|------------|
| Sync delegation | ✅ `delegate` tool | ✅ `delegate` tool | ✅ via event bus | ✅ `call_subordinate` |
| Async spawn | ❌ | ✅ `subagent_spawn` | ✅ `std.Thread.spawn` | ❌ |
| Pipeline | ✅ `>>` | ❌ | ❌ | ❌ |
| Parallel/Race | ✅ `Orchestrator` | ❌ (manual) | ❌ (manual) | ❌ |
| MessageBus | ✅ `coordination/bus.py` | ✅ | ✅ (event bus) | ❌ |
| Max depth guard | ❌ | ✅ `max_depth: 3` | ✅ `max_depth: 3` | ✅ `agent.number` |

### Orchestration Decision

**Keep sync `delegate`, add `max_depth`, skip async spawn.**

Rationale:
1. sage-agent's `delegate` tool is already well-designed — matches zeroclaw and agent-zero patterns exactly
2. Async spawn adds complexity without clear benefit — `Orchestrator.run_parallel()` covers programmatic use cases
3. Pipeline and Parallel/Race are **unique advantages** over all comparables — keep them
4. `max_depth` is the only gap that needs filling — prevents infinite delegation recursion

---

## Recommended Architecture

### Layered Design: AIEOS (Optional Identity) + Runtime Config

```
agents/
├── assistant.md              # Runtime config (frontmatter) + system prompt (body)
├── assistant.aieos.json      # Optional AIEOS v1.2 identity/persona
├── researcher.md
├── researcher.aieos.json
├── summarizer.md
└── summarizer.aieos.json
```

### config.toml Changes

```toml
[agents]
agent_path = "agents/"       # default: agents/ from CWD
primary = "assistant"        # filename stem (loads agents/assistant.md), required

[[agents.secondary]]
name = "researcher"          # filename stem (loads agents/researcher.md)
[[agents.secondary]]
name = "summarizer"

[defaults]
model = "azure_ai/kimi-k2.5"
max_turns = 10
max_depth = 3                # NEW: delegation chain depth limit

[defaults.model_params]
temperature = 0.0
max_tokens = 4096
```

### Per-Agent .md File (Updated Frontmatter)

```markdown
---
name: researcher
model: azure_ai/kimi-k2.5
max_turns: 20
max_depth: 2                  # NEW: per-agent override

# Optional AIEOS identity (loaded if file exists)
identity:
  format: aieos               # "aieos" | "none"
  file: researcher.aieos.json # relative to agent_path

permission:
  read: allow
  shell:
    "*": ask
    "git log*": allow
  web: allow
---

You are a deep research specialist...
```

### What Each Layer Provides

| Layer | Source | Purpose |
|-------|--------|---------|
| **AIEOS identity** (optional) | `<name>.aieos.json` | WHO: persona, psychology (neural_matrix, OCEAN), linguistics (text_style, catchphrases), capabilities (declarative skill discovery) |
| **Runtime config** | `<name>.md` frontmatter | HOW: model, provider, tools, permissions, memory, MCP, context, sandbox |
| **System prompt** | `<name>.md` body | WHAT: the system prompt sent to the LLM |
| **Global defaults** | `config.toml [defaults]` | Fallback for any unset runtime fields |
| **Agent overrides** | `config.toml [agents.<name>]` | Override runtime config for specific agents |

**Override priority (lowest → highest):**
1. `config.toml [defaults]`
2. `config.toml [agents.<name>]`
3. Agent `.md` frontmatter
4. AIEOS identity injects into system prompt (additive, never overrides runtime config)

---

## Implementation Decisions

Confirmed decisions from design discussion:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| AIEOS required or optional? | **Optional** | zeroclaw/nullclaw make it optional. Some agents don't need a persona. |
| Orchestration model | **Sync `delegate` (keep current)** | Already matches zeroclaw/agent-zero. Clean, proven, LLM-native. |
| Async spawn | **Skip for now** | `Orchestrator.run_parallel()` covers programmatic use case. Additive later. |
| Pipeline/Parallel/Race | **Keep** | Unique advantage over all comparables. |
| New: `max_depth` | **Add** | zeroclaw and nullclaw both have this. Prevents infinite delegation. Default 3. |
| Resolution tiers | **Single `agent_path`** | Sufficient for now. Can add multi-tier resolution later. |
| `agent_path` default | **`agents/` from CWD** | Matches agent-zero's directory-based approach. |

### Implementation Checklist

- [ ] Add `max_depth` to `AgentConfig` in `sage/config.py` (default: 3)
- [ ] Add `max_depth` to `[defaults]` in `sage/main_config.py`
- [ ] Enforce `max_depth` in `Agent.delegate()` — track current depth, raise `ToolError` if exceeded
- [ ] Add `identity` config to `AgentConfig` (optional `IdentityConfig` model)
- [ ] Create AIEOS loader in `sage/identity/` — parse `.aieos.json`, extract linguistics/psychology for system prompt injection
- [ ] Add `agent_path` to main config schema
- [ ] Add `primary` and `secondary` agent references to main config schema
- [ ] Update `Agent.from_config()` to resolve agents from `agent_path`
- [ ] Update `config.toml` discovery to read `[agents]` section
- [ ] Write tests for all new config paths
- [ ] Write tests for `max_depth` enforcement
- [ ] Write tests for AIEOS identity loading and system prompt injection
- [ ] Update `.docs/agent-authoring.md` with new config patterns

### Files to Modify

| File | Change |
|------|--------|
| `sage/config.py` | Add `max_depth`, `IdentityConfig` to `AgentConfig` |
| `sage/main_config.py` | Add `agent_path`, `primary`, `secondary` to main config schema; add `max_depth` to defaults |
| `sage/agent.py` | Enforce `max_depth` in `delegate()`; pass depth counter to subagents; load AIEOS identity into system prompt |
| `sage/identity/__init__.py` | New module |
| `sage/identity/aieos.py` | AIEOS v1.2 parser — extract relevant fields for system prompt |
| `sage/identity/models.py` | `IdentityConfig` Pydantic model |
| `config.toml` | Add `[agents]` section example |
| `.docs/agent-authoring.md` | Document new config patterns |

### External References

- AIEOS v1.2 schema: https://aieos.org/schema/v1.2/aieos.schema.json
- AIEOS GitHub: https://github.com/entitai/aieos
- agent-zero: https://github.com/agent0ai/agent-zero
- zeroclaw: https://github.com/zeroclaw-labs/zeroclaw
- nullclaw: https://github.com/nullclaw/nullclaw
- openclaw: https://github.com/openclaw/openclaw

# Documentation & Build Update Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update all project documentation to reflect hook/event/observability enhancements and the Node.js TUI, add Makefile targets for TUI build/install.

**Architecture:** Pure documentation and build config changes. ADR-012 captures the event telemetry architectural decision. README and TUI README get updated sections. Makefile gets TUI targets.

**Tech Stack:** Markdown, GNU Make, pnpm

---

### Task 1: Create ADR-012 — Event Telemetry and Observability

**Files:**
- Create: `.docs/adrs/012-event-telemetry-and-observability.md`

**Step 1: Write ADR-012**

Create `.docs/adrs/012-event-telemetry-and-observability.md` with these sections:

- **Status:** Accepted
- **Context:** The hook system (ADR-011) provides lifecycle control flow, but observability needs a canonical event model shared across hooks, telemetry, the JSON-RPC bridge, and the TUI. Issues: no canonical envelope, fragmented correlation IDs, no default telemetry, bridge inventing synthetic call IDs.
- **Decision:** Adopt a three-layer architecture:
  1. **Canonical EventEnvelope** (`sage/telemetry.py`) — Pydantic model wrapping every lifecycle event with version, event_id, event_name, category, phase, timestamp, agent_name, agent_path, run_id, turn_id, session_id, originating_session_id, parent/trigger event IDs, trace/span IDs, status, duration_ms, UsageSnapshot, payload dict, ErrorSnapshot.
  2. **Typed Event Dataclasses** (`sage/events.py`) — ToolStarted, ToolCompleted, LLMTurnStarted, LLMTurnCompleted, DelegationStarted, DelegationCompleted, LLMStreamDelta, BackgroundTaskCompleted. Each mapped to a HookEvent via EVENT_TYPE_MAP. Factory function `from_hook_data()` constructs typed instances from raw hook dicts.
  3. **Telemetry Pipeline** — `TelemetryRecorder` protocol records every lifecycle emission. `DefaultTelemetryRecorder` fans out to `EventSink` list and optional `EventPublisher`. `LoggingEventSink` for local visibility. `InMemoryEventPublisher` for tests. `NoOpEventPublisher` for production default.
  4. **ExecutionContext** (`sage/telemetry.py`) — Propagates run_id, session_id, originating_session_id, agent_path, delegation_depth, turn info through the agent tree. `root_execution_context()` at top-level run, `child_execution_context()` for delegations.
  5. **OpenTelemetry Integration** (`sage/tracing.py`) — `span()` async context manager yields real OTel spans when installed, no-op otherwise. `setup_tracing()` configures SDK from agent config. `current_trace_context()` copies trace/span IDs into envelopes.
  6. **Payload Sanitization** — `sanitize_payload()` redacts secrets (api_key, token, password, etc.), truncates strings >5000 chars, scrubs credentials via `scrub_text()`, caps recursion at depth 6.
- **Consequences:**
  - Positive: Full observability by default, session lineage is explicit, bridge becomes a projection layer, single event model feeds logs/UI/traces/metrics
  - Negative: More IDs to propagate, event volume increases (esp. stream deltas), moderate refactor of lifecycle emission
- **Extends:** ADR-011 (hook system), ADR-006 (asyncio parallelism)

Reference the deleted `docs/adr-0001-hook-observability-and-event-publishing.md` (commit d2e30b6) as the original proposal that motivated this work.

**Step 2: Verify**

Run: `cat .docs/adrs/012-event-telemetry-and-observability.md | head -5`
Expected: Shows `# ADR-012:` header and `Accepted` status.

**Step 3: Commit**

```bash
git add .docs/adrs/012-event-telemetry-and-observability.md
git commit -m "docs: add ADR-012 for event telemetry and observability"
```

---

### Task 2: Update README.md — TUI Section

**Files:**
- Modify: `README.md:137-142` (the TUI section)

**Step 1: Replace the TUI section**

The current TUI section (line ~137) says Textual and `sage tui`. Replace it with:

```markdown
### TUI

A full interactive terminal UI built with [Ink v6](https://github.com/vadimdemedes/ink) and React 19. Communicates with the Python backend via JSON-RPC over stdio. Block-based conversation display with live streaming, collapsible tool calls, markdown rendering, permission prompts, delegation hierarchy visualization, and an event timeline with inspector.

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
```

**Step 2: Verify**

Search README.md for "Textual" — should find zero matches.
Search README.md for "Ink v6" — should find one match in the TUI section.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README TUI section for Node.js/Ink TUI"
```

---

### Task 3: Update README.md — Architecture Section

**Files:**
- Modify: `README.md:452-497` (the Architecture section)

**Step 1: Add new modules to architecture tree**

After the `hooks/` entry, add:

```
  events.py         # Typed event dataclasses (ToolStarted, LLMTurnCompleted, …)
  telemetry.py      # EventEnvelope, TelemetryRecorder, ExecutionContext, sanitization
  tracing.py        # OpenTelemetry span() wrapper (real spans or no-op)
  protocol/         # JSON-RPC bridge to TUI (EventBridge, session, notifications)
```

Add a `tui/` section at the bottom of the tree:

```
tui/                # TypeScript terminal UI (Ink v6 + React 19)
  src/
    components/     # ConversationView, ActiveStreamView, EventTimeline, EventInspector, …
    integration/    # EventNormalizer, EventProjector, BlockEventRouter, LifecycleManager
    state/          # BlockContext + blockReducer (block-based state management)
    ipc/            # SageClient (JSON-RPC over stdio)
    renderer/       # Markdown + syntax-highlighted code blocks
    commands/       # Slash command registry (21 commands)
```

**Step 2: Verify**

Search README.md for "telemetry.py" — should find one match.
Search README.md for "EventNormalizer" — should find one match.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README architecture section with telemetry and TUI"
```

---

### Task 4: Update README.md — Hook System Section

**Files:**
- Modify: `README.md:99-114` (the Hook System section)

**Step 1: Add observability integration note**

After the existing hook code example (line ~114), add a paragraph:

```markdown
Every hook emission is also recorded as a canonical `EventEnvelope` by the telemetry layer (`sage/telemetry.py`). This gives full observability by default — each event carries correlation IDs (run_id, session_id, originating_session_id), timing, token usage, and a sanitized payload. The TUI's event timeline and inspector consume these envelopes via JSON-RPC for real-time visibility into agent behavior. See [ADR-012](.docs/adrs/012-event-telemetry-and-observability.md).
```

Also update the HookEvent list to include the newer events: `ON_DELEGATION_COMPLETE`, `ON_LLM_STREAM_DELTA`, `BACKGROUND_TASK_COMPLETED`, `ON_RUN_STARTED/COMPLETED/FAILED`, etc.

**Step 2: Verify**

Search README.md for "EventEnvelope" — should find one match in the hook section.
Search README.md for "ADR-012" — should find one match.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add observability integration note to hook system section"
```

---

### Task 5: Update README.md — Requirements Section

**Files:**
- Modify: `README.md:514-518` (the Requirements section)

**Step 1: Add TUI requirements**

The current requirements section only mentions Python. Add TUI requirements:

```markdown
## Requirements

- Python 3.10+
- See `pyproject.toml` for full dependency list

### TUI (optional)

- Node.js 22+
- pnpm 10+
- See `tui/package.json` for full dependency list
```

**Step 2: Verify**

Search README.md for "Node.js 22" — should find one match.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add TUI requirements to README"
```

---

### Task 6: Update tui/README.md — Architecture Diagram

**Files:**
- Modify: `tui/README.md:143-166` (the Architecture section)

**Step 1: Update architecture tree**

Replace the architecture tree to include the new event components:

```
tui/src/
├── index.tsx              # Entry point (Ink render)
├── components/            # React/Ink UI components
│   ├── App.tsx            # Root provider tree + layout
│   ├── ConversationView.tsx # Block-based conversation display
│   ├── InputPrompt.tsx    # Text input with slash command support
│   ├── ActiveStreamView.tsx # Live streaming content + tool indicators
│   ├── BottomBar.tsx      # Status bar (model, cost, context, agents)
│   ├── PermissionPrompt.tsx # Tool permission approval UI
│   ├── ToolDisplay.tsx    # Completed tool summary (ToolSummary-based)
│   ├── EventTimeline.tsx  # Event timeline with verbosity/filtering
│   ├── EventInspector.tsx # Event detail viewer with correlation IDs
│   ├── SlashCommands.tsx  # Fuzzy-filtered command overlay
│   ├── SessionPicker.tsx  # Session resume/history
│   ├── AgentTree.tsx      # Delegation hierarchy visualization
│   └── blocks/            # StaticBlock, UserBlock, TextBlock
├── state/                 # BlockContext + blockReducer (block-based state)
├── ipc/                   # SageClient (JSON-RPC over stdio)
├── integration/           # Event processing pipeline
│   ├── EventNormalizer.ts # Normalize raw RPC events to canonical EventRecord
│   ├── EventProjector.ts  # Project EventRecords to block state mutations
│   ├── BlockEventRouter.ts # Route events to block components
│   └── LifecycleManager.ts # Component lifecycle coordination
├── renderer/              # Markdown + syntax-highlighted code blocks
├── hooks/                 # useInputHistory, useResizeHandler, useMessageQueue
├── commands/              # Slash command registry (21 commands)
├── utils/                 # Terminal detection, Unicode fallback, string width
└── types/                 # Protocol, state, blocks, events
```

**Step 2: Verify**

Search `tui/README.md` for "EventTimeline" — should find one match.
Search `tui/README.md` for "EventNormalizer" — should find one match.

**Step 3: Commit**

```bash
git add tui/README.md
git commit -m "docs: update TUI README architecture with event components"
```

---

### Task 7: Add Makefile TUI Targets

**Files:**
- Modify: `Makefile`

**Step 1: Add TUI dependency check and targets**

Add to the `.PHONY` line: `check-tui-deps tui-install tui-build tui-dev tui-test tui-lint tui-install-global tui-clean`

Add after the existing targets:

```makefile
# ── TUI (Node.js / Ink) ──────────────────────────────────────────────────────

check-tui-deps:
	@which node >/dev/null 2>&1 || (echo "ERROR: Node.js 22+ is required for the TUI. Install: https://nodejs.org" && exit 1)
	@which pnpm >/dev/null 2>&1 || (echo "ERROR: pnpm 10+ is required for the TUI. Install: https://pnpm.io" && exit 1)
	@echo "TUI dependencies found."

tui-install: check-tui-deps
	cd tui && pnpm install

tui-build: tui-install
	cd tui && pnpm run build

tui-dev: tui-install
	cd tui && pnpm run dev

tui-test: tui-install
	cd tui && pnpm run test

tui-lint: tui-install
	cd tui && pnpm run lint
	cd tui && pnpm run typecheck

tui-install-global: tui-build
	cd tui && pnpm run install:global

tui-clean:
	rm -rf tui/dist tui/node_modules
```

**Step 2: Verify**

Run: `make -n tui-build` (dry run)
Expected: Shows the `cd tui && pnpm install` and `cd tui && pnpm run build` commands.

**Step 3: Commit**

```bash
git add Makefile
git commit -m "build: add Makefile targets for TUI build, test, and install"
```

---

### Task 8: Final Verification

**Step 1: Verify all docs render correctly**

- Check no broken internal links in README.md (ADR-012 link, tui/README.md link)
- Check the `.docs/adrs/` directory has 012 file
- Check Makefile targets are syntactically valid: `make -n tui-build`

**Step 2: Squash or leave as individual commits (user preference)**

The 7 commits from tasks 1-7 tell a clean story and can stay as-is.

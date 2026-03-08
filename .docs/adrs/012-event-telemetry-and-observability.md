# ADR-012: Event Telemetry and Observability

## Status
Accepted

## Context

The hook system (ADR-011) provides lifecycle control flow -- handlers can intercept and modify data at well-defined points in the agent run loop. However, hooks alone do not provide observability. Three problems remained after ADR-011:

1. **No canonical event schema.** Hook data is passed as untyped `dict` objects. Every consumer (TUI bridge, logging, metrics) had to invent its own interpretation of what fields exist, their types, and their meaning. The TUI bridge was already generating synthetic call IDs because the hook data did not carry them consistently.

2. **Fragmented correlation.** An agent run spans multiple LLM turns, tool calls, delegations, and potentially background tasks across sessions. There was no single correlation model linking `run_id`, `session_id`, `originating_session_id`, `turn_id`, and `event_id` together, nor any mechanism for propagating this context across delegation boundaries.

3. **No default telemetry.** Without explicit wiring, lifecycle events vanished silently. Debugging required ad-hoc logging hooks or print statements. There was no record-everything-by-default pipeline.

The original proposal (commit `d2e30b6`, `docs/adr-0001-hook-observability-and-event-publishing.md`) outlined the direction. This ADR documents what was actually implemented.

## Decision

A three-layer architecture layered on top of the existing hook system:

### Layer 1: Canonical EventEnvelope (`sage/telemetry.py`)

Every lifecycle event is wrapped in a single Pydantic model, `EventEnvelope`, carrying:

| Field group | Fields |
|---|---|
| **Identity** | `version`, `event_id` (uuid hex), `event_name`, `category`, `phase` |
| **Timing** | `timestamp` (epoch float), `duration_ms` |
| **Agent context** | `agent_name`, `agent_path` (list of strings tracing delegation chain) |
| **Correlation** | `run_id`, `turn_id`, `turn_index`, `session_id`, `originating_session_id`, `parent_event_id`, `trigger_event_id` |
| **Distributed tracing** | `trace_id`, `span_id` (hex strings from OTel when available) |
| **Outcome** | `status` (`ok` / `error` / `cancelled` / `skipped`), `error` (`ErrorSnapshot`), `usage` (`UsageSnapshot`) |
| **Data** | `payload` (sanitized dict) |

The `phase` field distinguishes event shape: `start`, `delta`, `complete`, `fail`, `cancel`, and `point` (for one-shot events with no duration).

Supporting models:
- `UsageSnapshot` -- prompt/completion/total/cache-read/cache-creation/reasoning tokens and cost.
- `ErrorSnapshot` -- exception type, message, retryable flag, optional provider code.

### Layer 2: Typed Event Dataclasses (`sage/events.py`)

Eight typed dataclasses bridge the untyped hook `dict` to structured events:

| Dataclass | HookEvent | Phase |
|---|---|---|
| `ToolStarted` | `PRE_TOOL_EXECUTE` | start |
| `ToolCompleted` | `POST_TOOL_EXECUTE` | complete |
| `LLMTurnStarted` | `PRE_LLM_CALL` | start |
| `LLMTurnCompleted` | `POST_LLM_CALL` | complete |
| `DelegationStarted` | `ON_DELEGATION` | start |
| `DelegationCompleted` | `ON_DELEGATION_COMPLETE` | complete |
| `LLMStreamDelta` | `ON_LLM_STREAM_DELTA` | delta |
| `BackgroundTaskCompleted` | `BACKGROUND_TASK_COMPLETED` | complete |

All dataclasses carry the correlation fields (`run_id`, `session_id`, `originating_session_id`, `agent_path`, `event_id`).

`EVENT_TYPE_MAP` maps each dataclass to its `HookEvent`. `from_hook_data(event_class, data)` constructs a typed instance from the raw hook dict using per-class factory lambdas.

### Layer 3: Telemetry Pipeline (`sage/telemetry.py`)

The recording pipeline follows a protocol-based design:

- **`TelemetryRecorder`** protocol -- `async record(envelope, data) -> EventEnvelope`.
- **`DefaultTelemetryRecorder`** -- the concrete implementation. On every `record()` call it sanitizes the payload, appends the envelope to an in-memory list, fans out to an optional `EventPublisher`, and writes to all registered `EventSink` instances. All publisher and sink errors are caught, logged at WARNING, and swallowed -- telemetry failures never crash the agent.
- **`EventPublisher`** protocol -- `async publish(envelope) -> PublishResult`. Two implementations: `NoOpEventPublisher` (returns immediately) and `InMemoryEventPublisher` (accumulates envelopes in a list, useful for testing).
- **`EventSink`** protocol -- `async write(envelope) -> None`. One implementation: `LoggingEventSink` (writes structured fields to a Python logger at DEBUG level).
- **`PublishResult`** -- `accepted`, `backend`, `message`.

### Correlation: ExecutionContext (`sage/telemetry.py`)

A `@dataclass(slots=True)` propagated via `contextvars.ContextVar`:

```python
@dataclass(slots=True)
class ExecutionContext:
    run_id: str
    session_id: str | None
    originating_session_id: str | None
    agent_path: list[str]
    delegation_depth: int
    current_turn: int | None
    current_turn_id: str | None
    current_event_id: str | None
```

Factory functions for context lifecycle:
- `root_execution_context(agent_name, session_id, ...)` -- creates the top-level context. If no `session_id` is provided, one is generated. `originating_session_id` defaults to `session_id`.
- `child_execution_context(parent, agent_name, ...)` -- creates a delegation child. Preserves `originating_session_id` from parent, increments `delegation_depth`, extends `agent_path`.
- `with_turn_context(ctx, turn)` -- returns a copy with `current_turn` and a deterministic `current_turn_id` (`{run_id}:turn:{turn}`).
- `with_event_context(ctx, event_id)` -- returns a copy with `current_event_id` set.
- `bind_execution_context(ctx)` -- context manager that sets/resets the `ContextVar`.

### Payload Sanitization (`sage/telemetry.py`)

`sanitize_payload(data)` processes every value before it enters an envelope:

1. Keys in `_REDACTED_KEYS` (`api_key`, `apikey`, `authorization`, `password`, `secret`, `token`, `access_token`, `refresh_token`) are replaced with `***REDACTED***`.
2. Strings are passed through `scrub_text()` (the credential scrubber from ADR-011's built-in hooks) and truncated at 5000 characters.
3. Pydantic models are dumped to dicts (excluding `raw_response` fields) and recursed.
4. Recursion is capped at depth 6 (`[max-depth]`).
5. Enums are reduced to their `.value`.
6. The `_event_envelope` key is excluded from payloads to avoid circular nesting.

### Distributed Tracing (`sage/tracing.py`)

OpenTelemetry integration as an optional dependency:

- `span(name, attributes)` -- async context manager yielding a real OTel span when `opentelemetry-api` is installed, or a `_NoOpSpan` (no-op stub with `set_attribute`, `record_exception`, `set_status` methods) when it is not. Callers never guard on tracing availability.
- `setup_tracing(config)` -- configures the OTel SDK from a `TracingConfig` object. Supports `console` (via `ConsoleSpanExporter`) and `otlp` (via `OTLPSpanExporter` over gRPC) exporters. Silent no-op when OTel packages are missing.
- `current_trace_context()` -- returns `(trace_id, span_id)` as hex strings from the active OTel span, or `(None, None)` when tracing is unavailable or no span is active.

### Extended HookEvent Enum (`sage/hooks/base.py`)

The `HookEvent` enum was expanded to 31 events across seven categories:

| Category | Events |
|---|---|
| **Run lifecycle** | `ON_RUN_STARTED`, `ON_RUN_COMPLETED`, `ON_RUN_FAILED`, `ON_RUN_CANCELLED` |
| **LLM calls** | `PRE_LLM_CALL`, `POST_LLM_CALL`, `ON_LLM_ERROR`, `ON_LLM_RETRY`, `ON_LLM_STREAM_DELTA` |
| **Tool execution** | `PRE_TOOL_EXECUTE`, `POST_TOOL_EXECUTE`, `ON_TOOL_FAILED`, `ON_TOOL_SKIPPED` |
| **Permissions** | `PRE_PERMISSION_CHECK`, `POST_PERMISSION_CHECK` |
| **Compaction** | `PRE_COMPACTION`, `POST_COMPACTION`, `ON_COMPACTION`, `ON_COMPACTION_FAILED` |
| **Memory** | `PRE_MEMORY_RECALL`, `POST_MEMORY_RECALL`, `PRE_MEMORY_STORE`, `POST_MEMORY_STORE`, `ON_MEMORY_ERROR` |
| **Delegation** | `ON_DELEGATION`, `ON_DELEGATION_COMPLETE`, `ON_DELEGATION_FAILED` |
| **Background tasks** | `ON_BACKGROUND_TASK_STARTED`, `BACKGROUND_TASK_COMPLETED`, `ON_BACKGROUND_TASK_FAILED`, `ON_BACKGROUND_TASK_CANCELLED` |
| **Sessions** | `ON_SESSION_STARTED`, `ON_SESSION_RESUMED`, `ON_SESSION_CLOSED` |
| **Coordination** | `ON_MESSAGE_SENT`, `ON_MESSAGE_RECEIVED`, `ON_MESSAGE_EXPIRED`, `ON_DEAD_LETTER` |
| **Planning** | `ON_PLAN_CREATED` |

### TUI Integration (TypeScript)

The TUI consumes events through a normalize-then-project pipeline:

- **`EventNormalizer`** (`tui/src/integration/EventNormalizer.ts`) -- converts raw JSON-RPC notifications into a canonical `EventRecord`. Handles two formats: the new `EVENT_EMITTED` envelope (direct field mapping) and legacy per-method notifications (`TOOL_STARTED`, `STREAM_DELTA`, etc.) which are mapped to canonical event names, categories, and phases via a `legacyEvent()` helper.

- **`EventProjector`** (`tui/src/integration/EventProjector.ts`) -- projects `EventRecord` instances into `BlockAction[]` for UI state mutations (stream deltas, tool start/complete, delegation start/complete, permission requests, system messages). Maintains a `pendingCalls` map to correlate tool starts with completions when explicit call IDs are absent.

- **`EventTimeline`** (`tui/src/components/EventTimeline.tsx`) -- React/Ink component displaying a scrollable event timeline. Supports verbosity filtering (`eventVisibleAtVerbosity`) and category/status filters (`eventMatchesFilters`). Shows category-colored labels, event summaries, duration, and token usage.

- **`EventInspector`** (`tui/src/components/EventInspector.tsx`) -- detail panel for a selected event. Displays correlation IDs (`run`, `session`, `originating session`, `turn`), agent path, duration, usage, error details, and a truncated payload dump.

## Consequences

**Positive:**

- **Full observability by default.** `DefaultTelemetryRecorder` records every lifecycle event without explicit opt-in. The in-memory event list is always available for debugging, testing, and post-run analysis.
- **Single event model.** `EventEnvelope` is the one schema consumed by the TUI, logging sinks, and any future external publisher. No more per-consumer field interpretation.
- **Explicit session lineage.** `originating_session_id` is set once at the root and preserved across all delegations, making it possible to trace an entire conversation tree back to the user session that started it.
- **Bridge becomes projection.** The TUI bridge no longer invents its own event semantics. `EventNormalizer` maps envelopes to `EventRecord`; `EventProjector` maps records to UI actions. Each layer has a single responsibility.
- **Sanitization is mandatory.** Every payload passes through `sanitize_payload()` before entering an envelope. Secrets are redacted, large strings are truncated, and recursion is bounded. There is no code path that emits unsanitized data.
- **OTel is zero-cost optional.** `span()` and `current_trace_context()` work unconditionally. When the OTel SDK is not installed, they degrade to no-ops with no import errors or conditional guards in the calling code.

**Negative:**

- **More IDs to propagate.** `ExecutionContext` carries eight fields. Every delegation boundary and turn transition must create a new context copy. Forgetting to propagate context results in missing correlation, not a crash -- silent data loss.
- **Event volume.** `LLMStreamDelta` events fire per-chunk during streaming. For long responses this produces high event volume. The TUI mitigates this with verbosity filtering, but the in-memory event list grows unboundedly during a run.
- **Moderate runtime refactor.** Integrating `ExecutionContext`, `TelemetryRecorder`, and `span()` into the agent run loop required touching call sites that previously only emitted void hooks. The hook system itself (ADR-011) is unchanged, but the agent code around it grew.

## Extends
- ADR-011 (`011-hook-event-system.md`) -- hooks provide the lifecycle interception points; this ADR adds the observability layer on top
- ADR-006 (`006-asyncio-parallelism.md`) -- all telemetry recording, publishing, and sink operations are async

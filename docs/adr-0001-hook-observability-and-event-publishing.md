# ADR-0001: Hook Observability and Event Publishing Architecture

## Status

Proposed

## Date

2026-03-07

## Context

The current hook system is useful as a lightweight lifecycle callback mechanism, but it does not provide a reliable foundation for full observability or future distributed event delivery.

Current issues in the implementation:

- Runtime lifecycle emission only uses void dispatch for normal agent events, so modifying hooks do not affect live execution for `PRE_LLM_CALL` and `POST_LLM_CALL`.
- Several hook events exist in `HookEvent` but are never emitted in runtime paths.
- Tool and delegation events lack stable correlation identifiers.
- Session lineage is fragmented across agent-local state, background task state, and JSON-RPC server state.
- EventBridge, tracing, background task tracking, and coordination bus all expose partial observability, but there is no canonical event envelope shared across them.
- The in-memory coordination bus is useful for local orchestration, but it is not the right primitive to embed into hook control flow directly.

The project now needs:

- telemetry enabled by default for every emitted hook
- a consistent event schema that captures what happened, what triggered it, how long it took, token usage, current session, originating session, and related identifiers when available
- a design that preserves low-latency local control flow while allowing future publication to a distributed backend

## Decision Drivers

- Hook control flow must remain local and deterministic.
- Observability must be complete by default, not opt-in per feature.
- Event payloads must support correlation across runs, turns, tools, delegations, and sessions.
- The design must not make remote delivery part of the critical path for agent execution.
- Existing tracing support should complement the event model, not compete with it.
- Migration should be incremental and testable.

## Considered Options

### Option 1: Keep hooks as-is and add more ad hoc bridge notifications

Pros:

- Smallest short-term change
- Minimal refactor to agent runtime

Cons:

- Preserves current fragmentation
- Does not solve modifying-hook correctness
- Produces duplicated schemas across hooks, bridge notifications, and tracing
- Makes distributed publishing harder later

### Option 2: Replace hooks with a distributed event bus

Pros:

- Unified story for publication and observability
- Natural path to multi-process and multi-node coordination

Cons:

- Wrong abstraction for in-process control flow
- Introduces remote latency and partial-failure concerns into the agent loop
- Modifying hooks become difficult or unsafe
- Requires much larger operational surface area

### Option 3: Keep hooks local, add a canonical event envelope, and publish asynchronously via a transport abstraction

Pros:

- Preserves safe local control flow
- Enables telemetry by default
- Clean path to future Redis, NATS, Kafka, or OTLP-backed publishing
- Supports both local sinks and remote sinks from the same event model

Cons:

- Requires a moderate refactor of lifecycle emission
- Introduces a new event schema and publisher layer to maintain

## Decision

Adopt Option 3.

The architecture will separate two concerns:

1. Local hook execution for agent control flow and mutation
2. Asynchronous event publication for telemetry and downstream consumers

Hooks will remain in-process. Every emitted lifecycle event will be wrapped in a canonical `EventEnvelope` and sent to a default telemetry pipeline. Publication to external transports will be best-effort and non-blocking relative to the main agent loop.

## Decision Details

### 1. Canonical Event Envelope

Introduce a structured event model shared by hooks, telemetry, bridge notifications, and future publishers.

```python
@dataclass(slots=True)
class EventEnvelope:
    event_id: str
    event_name: str
    category: Literal[
        "run",
        "llm",
        "tool",
        "memory",
        "compaction",
        "delegation",
        "permission",
        "background",
        "session",
        "coordination",
        "planning",
    ]
    phase: Literal["start", "delta", "complete", "fail", "cancel", "point"]
    timestamp: float

    agent_name: str
    agent_path: list[str]
    run_id: str
    turn_id: str | None
    turn_index: int | None

    session_id: str | None
    originating_session_id: str | None
    parent_event_id: str | None
    trigger_event_id: str | None
    trace_id: str | None
    span_id: str | None

    status: Literal["ok", "error", "cancelled", "skipped"] | None
    duration_ms: float | None

    usage: UsageSnapshot | None
    payload: dict[str, Any]
    error: ErrorSnapshot | None
```

Supporting value objects:

- `UsageSnapshot`: prompt, completion, total, cache read, cache creation, reasoning, cost
- `ErrorSnapshot`: type, message, retryable, provider_code
- `SessionLineage`: optional helper for current and origin session values if the envelope grows too wide

Rules:

- Every event gets a unique `event_id`.
- Start and completion/failure events share logical correlation via `parent_event_id` or a dedicated operation ID in `payload`.
- `payload` contains event-specific fields only; shared observability data stays at top level.

### 2. Hook Execution Semantics

Split lifecycle emission into two explicit phases:

1. modifying hooks
2. void hooks

Recommended API:

```python
@dataclass(slots=True)
class HookDispatchResult:
    data: dict[str, Any]
    envelope: EventEnvelope

async def emit_lifecycle_event(
    self,
    event: HookEvent,
    data: dict[str, Any],
    *,
    envelope: EventEnvelope,
) -> HookDispatchResult:
    updated = await self._hook_registry.emit_modifying(event, data)
    await self._hook_registry.emit_void(event, updated)
    await self._telemetry.record(envelope, updated)
    return HookDispatchResult(data=updated, envelope=envelope)
```

Behavior:

- modifying hooks may mutate lifecycle input or output
- void hooks are side-effect-only
- telemetry records the final emitted payload after modification
- recursive-emit guards remain local to the registry

This is required to make notepad injection, auto-memory injection, query classification, and follow-through function correctly in the live agent loop.

### 3. Telemetry by Default

Add a default telemetry recorder that subscribes to all lifecycle emissions. This is not optional at the architecture level; configuration may change sink destinations, sampling for high-volume payloads, or retention, but not whether events exist.

Recommended interfaces:

```python
class TelemetryRecorder(Protocol):
    async def record(self, envelope: EventEnvelope, data: dict[str, Any]) -> None: ...

class EventPublisher(Protocol):
    async def publish(self, envelope: EventEnvelope) -> None: ...

class EventSink(Protocol):
    async def write(self, envelope: EventEnvelope) -> None: ...
```

Default stack:

- `InMemoryTelemetryRecorder` for tests
- `LoggingEventSink` for local visibility
- `JsonRpcEventSink` for TUI updates
- `TracingEventSink` to enrich OTel spans
- optional `PublisherBackedTelemetryRecorder` for transport-backed publication

### 4. Hook Taxonomy

Normalize lifecycle hooks into paired start/complete/fail events where possible.

Required event set:

- Run
  - `ON_RUN_STARTED`
  - `ON_RUN_COMPLETED`
  - `ON_RUN_FAILED`
  - `ON_RUN_CANCELLED`
- LLM
  - `PRE_LLM_CALL`
  - `POST_LLM_CALL`
  - `ON_LLM_STREAM_DELTA`
  - `ON_LLM_ERROR`
  - `ON_LLM_RETRY`
- Tool
  - `PRE_TOOL_EXECUTE`
  - `POST_TOOL_EXECUTE`
  - `ON_TOOL_FAILED`
  - `ON_TOOL_SKIPPED`
- Permission
  - `PRE_PERMISSION_CHECK`
  - `POST_PERMISSION_CHECK`
- Memory
  - `PRE_MEMORY_RECALL`
  - `POST_MEMORY_RECALL`
  - `PRE_MEMORY_STORE`
  - `POST_MEMORY_STORE`
  - `ON_MEMORY_ERROR`
- Compaction
  - `PRE_COMPACTION`
  - `POST_COMPACTION`
  - `ON_COMPACTION_FAILED`
- Delegation
  - `ON_DELEGATION`
  - `ON_DELEGATION_COMPLETE`
  - `ON_DELEGATION_FAILED`
- Background
  - `ON_BACKGROUND_TASK_STARTED`
  - `BACKGROUND_TASK_COMPLETED`
  - `ON_BACKGROUND_TASK_FAILED`
  - `ON_BACKGROUND_TASK_CANCELLED`
- Session
  - `ON_SESSION_STARTED`
  - `ON_SESSION_RESUMED`
  - `ON_SESSION_CLOSED`
- Coordination
  - `ON_MESSAGE_SENT`
  - `ON_MESSAGE_RECEIVED`
  - `ON_MESSAGE_EXPIRED`
  - `ON_DEAD_LETTER`
- Planning
  - `ON_PLAN_CREATED`
  - optional follow-up plan mutation events later

Guidance:

- Keep existing names where already public unless they are clearly inconsistent.
- Prefer additive migration over renaming existing public events immediately.

### 5. Correlation and Lineage

Make correlation fields first-class in runtime state.

Add an execution context object:

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

Rules:

- each top-level `run()` or `stream()` gets a new `run_id`
- `session_id` identifies the active conversation or delegated work session
- `originating_session_id` is copied from the root session that started the work tree
- subagent delegations inherit `run_id` or derive a child run ID, but must preserve `originating_session_id`
- background tasks persist both their own `session_id` and the root `originating_session_id`

Applicability and feasibility:

- `current session`: feasible once the runtime adopts a canonical execution context
- `originating session`: feasible only if root-run entrypoints assign one and delegation/background paths propagate it explicitly
- `what triggered it`: feasible as `trigger_event_id` for lifecycle causality, and as event-specific fields such as `trigger = "tool_call"` or `trigger = "background_notification"`

### 6. Usage and Duration Capture

Capture usage and timing consistently:

- LLM events:
  - full provider usage snapshot when available
  - model name
  - tool count
  - streaming token usage only when provider reports it
- Tool events:
  - wall-clock duration
  - tool call ID
  - permission outcome if applicable
  - token usage only if the tool itself reports usage
- Memory and compaction:
  - duration
  - result counts
  - strategy used
- Delegation:
  - duration
  - delegated agent
  - category/model routing if applied

Important constraint:

- "tokens spent" is universally reliable for LLM and some model-backed sub-operations
- it is not universally reliable for arbitrary tools unless tools can optionally return a usage snapshot

Recommended extension:

```python
@dataclass(slots=True)
class ToolExecutionResult:
    output: str
    usage: UsageSnapshot | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

### 7. Tracing Relationship

Tracing remains complementary.

- spans stay useful for timing and distributed tracing systems
- event envelopes become the canonical product-level observability record
- telemetry sinks may enrich current spans with event IDs, run IDs, session IDs, and status
- if OTel is available, `trace_id` and `span_id` should be copied into event envelopes

This keeps tracing optional at runtime while keeping event telemetry mandatory.

### 8. Event Publisher Abstraction

Do not couple hooks directly to `MessageBus`.

Introduce a transport-neutral publisher interface:

```python
class EventPublisher(Protocol):
    async def publish(self, envelope: EventEnvelope) -> PublishResult: ...
```

Implementations:

- `InMemoryEventPublisher`
- `RedisEventPublisher`
- `NatsEventPublisher`
- `KafkaEventPublisher`
- `NoOpEventPublisher`

Publisher requirements:

- best-effort async delivery by default
- bounded buffering and backpressure strategy
- retry policy isolated from the agent loop
- dead-letter support for durable transports
- explicit serialization versioning

Non-goals for the first implementation:

- exactly-once delivery
- remote modifying hooks
- cross-node synchronous control flow

### 9. Future of the Current MessageBus

The current `MessageBus` should not be deleted. It should be narrowed to coordination semantics and wrapped behind an interface.

Recommended split:

- `CoordinationBus`: task and control messages between agents
- `EventPublisher`: observability event publication

This allows the existing in-memory bus to remain useful for local multi-agent workflows while future distributed systems can replace either side independently.

### 10. Bridge and UI Integration

EventBridge should consume canonical envelopes rather than reconstructing correlation locally.

Changes:

- stop inventing tool `callId` values from tool names
- use real `tool_call_id` from event payloads
- include `run_id`, `session_id`, and `originating_session_id` in UI notifications where relevant
- stop reporting hardcoded durations for delegation events

The bridge becomes a projection layer over telemetry, not a parallel observability system.

## Consequences

### Positive

- Full observability becomes default behavior.
- Modifying hooks become correct and testable.
- A single event model can feed logs, UI, traces, metrics, and future distributed consumers.
- Session lineage and causality become explicit rather than inferred.
- Distributed publishing can be added without changing hook semantics.

### Negative

- Runtime event emission becomes more structured and more invasive than the current helper.
- More IDs and state need to be propagated through agent execution.
- Event volume will increase substantially, especially for stream deltas and high-frequency tool activity.

### Risks

- Excess payload size if raw messages and tool outputs are emitted indiscriminately
- confusion between operational tracing and product telemetry
- fragile migration if some paths keep using old ad hoc payloads

Mitigations:

- define redaction and payload size rules up front
- keep canonical envelope versioned
- migrate the bridge and tests early so downstream assumptions stay aligned

## Migration Plan

### Phase 1: Correctness Foundation

- Add `ExecutionContext` to agent runtime.
- Replace `_emit()` with a lifecycle emitter that runs modifying then void handlers.
- Fix built-in hook registration to mark modifying hooks correctly.
- Add integration tests proving live mutation of `PRE_LLM_CALL` and `POST_LLM_CALL`.

### Phase 2: Canonical Events

- Introduce `EventEnvelope`, `UsageSnapshot`, and `ErrorSnapshot`.
- Add `run_id`, `turn_id`, `tool_call_id`, and session lineage propagation.
- Emit missing memory and compaction lifecycle events.
- Add failure events for tool, LLM, delegation, and background paths.

### Phase 3: Default Telemetry

- Introduce `TelemetryRecorder` with an in-memory and logging implementation.
- Record every emitted event by default.
- Add redaction rules for secrets and large payload trimming.
- Update tests to assert canonical event content.

### Phase 4: Bridge Refactor

- Make EventBridge consume canonical envelopes.
- Remove bridge-side synthetic call correlation.
- Surface run/session lineage in TUI notifications.

### Phase 5: Publisher Abstraction

- Add `EventPublisher` interface and `InMemoryEventPublisher`.
- Add optional async publication pipeline.
- Keep publication outside the critical path.

### Phase 6: Distributed Backends

- Add Redis or NATS first, then evaluate Kafka only if event volume and durability needs justify it.
- Add dead-letter and retry configuration.
- Add consumer-side projections for metrics or audit storage.

## Testing Requirements

- Integration test: modifying `PRE_LLM_CALL` hook changes live messages passed to provider
- Integration test: modifying `PRE_LLM_CALL` hook changes live model selection
- Integration test: modifying `POST_LLM_CALL` hook can trigger retry behavior
- Integration test: every declared lifecycle hook is either emitted or explicitly deprecated
- Integration test: repeated parallel tool calls with same tool name correlate correctly via `tool_call_id`
- Integration test: delegated and background work preserve `originating_session_id`
- Unit test: telemetry recorder sees the final post-modification payload
- Unit test: publisher failures do not break the main agent loop

## Implementation Notes

- Treat stream delta events as high-volume and allow reduced payload sinks where needed.
- Telemetry payloads should be redacted before sink delivery, not after.
- Keep hook registry focused on execution semantics; do not overload it with transport logic.
- Preserve backward compatibility for existing `agent.on(...)` consumers by adapting typed events from canonical envelopes during migration.

## Follow-Up Work

- ADR for redaction and retention policy
- ADR for distributed publisher backend selection
- implementation ticket for lifecycle emitter refactor
- implementation ticket for canonical session lineage

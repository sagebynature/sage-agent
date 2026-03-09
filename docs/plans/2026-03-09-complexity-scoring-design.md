# Complexity Scoring Design

## Summary

This design adds an OpenFang-inspired complexity scoring system to Sage for each LLM turn. The score is computed from the effective turn input, emitted through Sage's event and telemetry pipeline, and surfaced in the TUI. The score is diagnostic in this phase. It does not change model selection yet.

The implementation is intentionally decoupled from routing policy so the same scoring substrate can be reused later when Sage redesigns Smart Routing.

## Goals

- Add a deterministic complexity score for each effective LLM turn
- Follow OpenFang's documented heuristics closely for the initial default behavior
- Make the scoring model configurable rather than hardcoded
- Emit the score in relevant Sage lifecycle events and telemetry payloads
- Surface the score in the TUI in compact and detailed forms
- Preserve a clean boundary so later Smart Routing can consume this signal without reworking the scoring implementation

## Non-Goals

- Automatic model routing in this phase
- Replacing the existing query-classifier hook in this phase
- Introducing new user-facing routing categories such as `quick` or `deep`
- Exposing complexity metadata in assistant response text
- Building a complete policy engine around the score in this phase

## Current State

Sage currently has two related but separate capabilities:

- explicit category-based delegation routing via `delegate(..., category=...)`
- optional rule-based query classification that can swap the model in `PRE_LLM_CALL`

Neither feature computes or emits a reusable complexity signal. There is no structured per-turn score that explains how difficult the effective LLM request appears based on prompt size, tool availability, code markers, or conversation depth.

The runtime already has a strong insertion point for this feature. `PRE_LLM_CALL` in `sage/agent.py` emits the effective `model`, `messages`, and `tool_schemas` that will be used for the call after prior modifications have been applied. The TUI already consumes canonical event payloads from telemetry and renders event summaries, inspectors, and active-stream status panels.

## Decision 1: Introduce A First-Class ComplexityScore Model

Sage will add a typed runtime model representing the complexity assessment for a single LLM turn.

Initial shape:

```python
class ComplexityLevel(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class ComplexityFactor(BaseModel):
    kind: str
    contribution: int
    value: int | float | str | bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ComplexityScore(BaseModel):
    score: int
    level: ComplexityLevel
    version: str
    factors: list[ComplexityFactor] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### Required behavior

- `score` is the total integer score for the turn
- `level` is derived from thresholds, not independently assigned
- `version` identifies the heuristic definition used to compute the score
- `factors` preserve explainability and support later UI/observability use cases
- `metadata` carries compact supporting counts such as tool count or message character totals

### Rationale

- A bare integer is too weak for debugging and future evolution
- Versioning makes threshold or weight changes auditable
- Factor attribution is necessary for operator trust and later routing analysis

## Decision 2: Implement A Pure Complexity Scoring Engine

The score computation will live in a dedicated backend module instead of inside routing logic or UI code.

Suggested module location:

- `sage/complexity.py`

Suggested entrypoint:

```python
def score_turn_complexity(
    *,
    messages: list[Message],
    tool_schemas: list[ToolSchema] | None,
    config: ComplexityConfig,
) -> ComplexityScore:
    ...
```

The scorer must be pure with respect to its inputs. Given the same effective messages, tool schemas, and config, it should always return the same result.

### Initial heuristics

The default implementation should track OpenFang's documented approach closely:

- message length contribution
- available tool count contribution
- code marker contribution
- deep conversation history contribution
- long system prompt contribution

The first pass should use these factors only. Additional Sage-specific factors can be added later under versioned config.

### Input semantics

The scorer will operate on the effective LLM inputs for the current turn:

- effective messages after any `PRE_LLM_CALL` modifications already applied
- effective tool schemas for the turn
- the actual system prompt text contained in effective messages

This avoids divergence between what Sage scores and what Sage actually sends to the provider.

## Decision 3: Add Configurable Complexity Heuristics

Sage will introduce a new config section for complexity scoring. The design must support customization from the first implementation, even if the default values mirror OpenFang.

Suggested config shape:

```toml
[complexity]
enabled = true
version = "openfang-v1"
simple_threshold = 100
complex_threshold = 500

[complexity.weights]
message_chars_divisor = 4
tool_count = 20
code_marker = 30
history_message_overage = 15
system_prompt_overage_divisor = 10

[complexity.features]
message_length = true
tool_count = true
code_markers = true
conversation_depth = true
system_prompt_length = true

code_markers = ["def ", "class ", "async ", "```", "SELECT ", "function "]
history_baseline_messages = 10
system_prompt_baseline_chars = 500
```

### Merge behavior

- top-level defaults come from `config.toml`
- per-agent overrides may be added later if needed, but are not required for phase 1
- if `enabled = false`, complexity scoring is skipped entirely

### Rationale

- matching OpenFang closely is useful, but hardcoded constants would make future tuning painful
- feature toggles reduce rollout risk
- configurable markers make the heuristic practical across code and non-code tasks

## Decision 4: Compute Complexity At The LLM Boundary

Complexity will be computed in the LLM turn execution path in `sage/agent.py`, adjacent to the existing `PRE_LLM_CALL` and `POST_LLM_CALL` emission points.

Recommended execution point:

1. emit `PRE_LLM_CALL` with baseline data
2. resolve the effective `model`, `messages`, and `tool_schemas`
3. compute `ComplexityScore` from those effective inputs
4. attach the score to the same turn's event payloads

In practice, this means the score is computed after effective inputs are known and before the provider call starts.

### Required event behavior

- `PRE_LLM_CALL` includes the resolved complexity object
- `POST_LLM_CALL` includes the same resolved complexity object
- the score is attached to the turn, not recomputed differently after completion

### Why not compute earlier

Computing from the initial message list would be wrong whenever hooks modify the prompt, context, or tool list. The LLM boundary is the only place where Sage has the canonical effective input set.

## Decision 5: Extend Typed Events And Telemetry Payloads

The complexity object will be promoted to a first-class field in typed LLM events rather than remaining an untyped payload convention.

Files expected to change:

- `sage/models.py`
- `sage/events.py`
- `sage/agent.py`
- `sage/telemetry.py`

### Typed event changes

Add `complexity: ComplexityScore | None = None` to:

- `LLMTurnStarted`
- `LLMTurnCompleted`

Factory helpers in `sage/events.py` must deserialize the structured payload into typed event objects.

### Telemetry payload behavior

- retain the full structured complexity object in the event payload
- avoid flattening the factor list into summary-only strings
- preserve compatibility for consumers that ignore the new field

### Rationale

- typed fields improve downstream correctness
- telemetry needs the full object for later Smart Routing analysis and UI inspection

## Decision 6: Extend Protocol Bridge And TUI Types

The JSON-RPC bridge and TUI event types will expose the complexity object so the frontend can render it without scraping ad hoc payload text.

Files expected to change:

- `sage/protocol/bridge.py`
- `tui/src/types/events.ts`
- `tui/src/types/protocol.ts`

### Bridge behavior

- `turn/started` should include compact complexity metadata for the current turn
- `turn/completed` should include the same complexity metadata
- canonical telemetry `event/emitted` payloads already carry event payloads, so the bridge should keep the complexity object intact there as well

### Rationale

- the TUI already consumes canonical event records
- explicit typing avoids frontend drift and payload-shape ambiguity

## Decision 7: Surface Complexity In The TUI Without Polluting Output

The TUI should render complexity where runtime metadata already belongs rather than mixing it into conversational content.

### Primary display surfaces

- `EventTimeline`
- `EventInspector`
- `ActiveStreamView`

### Display rules

`EventTimeline`

- show a compact badge for LLM events, for example `C42 medium`
- only render on LLM-related rows to avoid repetition elsewhere

`EventInspector`

- show the full structured complexity payload
- include factor contributions and supporting metadata
- keep raw JSON available if needed

`ActiveStreamView`

- show the current turn's complexity score and level while the model is thinking
- do not show the full factor breakdown in the active stream area

### Explicit non-goals for TUI display

- no complexity text inside assistant message blocks
- no complexity text in tool result previews
- no new standalone pane for this phase

### Rationale

- event and status panes already communicate system/runtime state
- keeping complexity out of output blocks preserves transcript cleanliness

## Interaction With Future Smart Routing

This design is a prerequisite for the later Smart Routing redesign, but it intentionally stops short of routing decisions.

Future Smart Routing should consume:

- `ComplexityScore`
- routing config and thresholds
- cost or latency policy
- model capability metadata

Future Smart Routing should not need to re-derive complexity from raw messages. That logic belongs in one place only.

### Design rule

Complexity scoring produces a signal.

Smart Routing will later map that signal to policy.

This separation avoids coupling observability, scoring, and routing into one hard-to-change subsystem.

## Alternatives Considered

### Alternative 1: Compute Complexity Only In The TUI

Rejected because the backend must be the source of truth for telemetry, hooks, and future routing.

### Alternative 2: Store Only An Integer Score

Rejected because explainability and versioning matter more than minimal payload size.

### Alternative 3: Implement Complexity As A Routing Hook First

Rejected because it couples a new heuristic directly to model behavior before the score is observable and testable.

### Alternative 4: Reuse Existing Query Classifier For Complexity

Rejected because the classifier is rule-based routing logic, not a reusable turn analysis model.

## Risks

### Payload growth

Adding factor breakdowns to every LLM turn event increases payload size. This is acceptable for now, but factor metadata should stay concise.

### User confusion

If the TUI displays complexity too prominently before routing behavior exists, users may assume it already affects model choice. Labels and placement should make it clear this is turn metadata.

### Heuristic drift

If Sage later adds extra factors without versioning, comparisons across runs become unreliable. The score must include a stable `version`.

### Test brittleness

Hardcoding exact scores across many tests can make future tuning expensive. Tests should focus on factor behavior, threshold mapping, and event propagation rather than snapshotting every numeric detail.

## Implementation Plan

### Phase 1: Models And Config

- add complexity models to `sage/models.py`
- add complexity config to `sage/config.py`
- add config tests for defaults and validation

### Phase 2: Scoring Engine

- implement `score_turn_complexity()`
- add unit tests for factor contributions and threshold derivation

### Phase 3: Agent And Event Integration

- compute complexity in the LLM turn path
- attach complexity to `PRE_LLM_CALL` and `POST_LLM_CALL`
- extend typed events and telemetry handling

### Phase 4: Protocol And TUI

- extend JSON-RPC bridge payloads
- update TUI event typings
- render compact and detailed displays in timeline, inspector, and active stream

### Phase 5: Verification

- backend unit tests
- event propagation tests
- bridge serialization tests
- TUI rendering tests

## Testing Strategy

### Backend scoring tests

- message length increases score predictably
- more tools increase score predictably
- code markers contribute predictably
- conversation depth over baseline contributes predictably
- long system prompts contribute predictably
- threshold mapping produces the expected `simple`, `medium`, and `complex` levels

### Event tests

- `PRE_LLM_CALL` includes complexity
- `POST_LLM_CALL` includes the same complexity for the same turn
- typed event adapters deserialize the complexity object correctly

### Protocol tests

- `event/emitted` contains the structured complexity payload
- `turn/started` and `turn/completed` notifications preserve compact complexity data

### TUI tests

- timeline renders the compact score badge on LLM events
- inspector shows complexity details
- active stream shows current-turn complexity while thinking

## Files Likely To Change

- `sage/models.py`
- `sage/config.py`
- `sage/agent.py`
- `sage/events.py`
- `sage/protocol/bridge.py`
- `tests/test_config.py`
- `tests/test_agent.py`
- `tests/test_events.py`
- `tui/src/types/events.ts`
- `tui/src/types/protocol.ts`
- `tui/src/components/EventTimeline.tsx`
- `tui/src/components/EventInspector.tsx`
- `tui/src/components/ActiveStreamView.tsx`
- relevant TUI tests

## Open Questions

- whether complexity config should support per-agent overrides in phase 1 or wait until Smart Routing work
- whether `turn/started` bridge notifications should include the full factor breakdown or only compact metadata
- whether event summaries should show only numeric score or score plus level by default

## Recommended Immediate Next Step

Implement phase 1 and phase 2 first:

- add the complexity models and config
- implement the pure scorer with tests

That work is low-risk, routing-neutral, and gives the rest of the implementation a stable contract.

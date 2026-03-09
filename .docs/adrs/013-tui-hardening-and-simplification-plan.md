# ADR-013: TUI Hardening and Simplification Plan

## Status
Proposed

## Context

The `@sage-agent/tui` package has a solid test baseline and a clear package boundary, but the current implementation has a few correctness and maintainability risks:

1. Permission handling is split between backend session logic and a frontend singleton store, which creates drift in trust boundaries.
2. Permission prompts are rendered concurrently and each prompt listens to global keyboard input, which can cause one keypress to affect multiple pending requests.
3. Risk classification and permission payload typing in the TUI do not fully match the backend protocol.
4. Slash command discovery and execution are defined in separate places, creating metadata drift and unnecessary duplication.
5. Tool completion correlation falls back to tool-name matching, which is brittle under concurrency.
6. `AppShell` currently owns too many responsibilities: connection lifecycle, command execution, event projection wiring, keyboard control flow, and layout.
7. The TUI contains two subprocess lifecycle abstractions (`SageClient` and `LifecycleManager`) without a clear single owner.

The review found no immediate test failures, but these issues increase the chance of subtle behavioral regressions as the TUI grows.

## Decision

Implement the TUI improvements in seven phases, ordered by user-facing risk and dependency.

### Phase 1: Fix permission correctness and input exclusivity

- Remove UI-side authority for session-scoped approvals.
- Keep backend permission/session state as the source of truth.
- Ensure only one permission prompt is active at a time, or otherwise guarantee exclusive input ownership.

Acceptance criteria:

- Session-scoped approvals do not survive `/reset` or session changes unless the backend explicitly allows them.
- A single permission keypress can resolve at most one pending permission request.

### Phase 2: Align permission protocol and risk typing

- Update TUI permission types to match backend-supported values, including `critical` risk where emitted.
- Normalize `permission/respond` request typing and field names around the actual backend contract.

Acceptance criteria:

- Critical-risk actions render as critical in the TUI.
- TUI request typing reflects the payload shape accepted by the backend.

### Phase 3: Unify slash-command metadata and execution

- Replace the split command registry/switch implementation with a single command system that owns:
  - metadata
  - aliases
  - argument parsing
  - execution handler
  - help text generation

Acceptance criteria:

- New commands are added in one place.
- Command palette entries and command behavior cannot drift independently.

### Phase 4: Harden tool/event correlation

- Replace name-only fallback correlation for tool completions with a stronger compound key such as explicit call ID, else `runId + agentPath + toolName`.
- When correlation is impossible, prefer rendering an orphan event/system message over mutating the wrong tool state.

Acceptance criteria:

- Concurrent same-name tool calls from different runs or delegates do not cross-complete in the UI.

### Phase 5: Split `AppShell` responsibilities

- Extract command execution, connection/bootstrap behavior, keyboard leader handling, and event-selection derivation out of the root component.
- Leave `AppShell` primarily responsible for composition and layout.

Acceptance criteria:

- Core app control flow is testable without rendering the full TUI.
- The root component is materially smaller and easier to reason about.

### Phase 6: Remove duplicate lifecycle abstractions

- Audit `LifecycleManager` versus `SageClient`.
- Keep one process-management abstraction and remove or merge the other.

Acceptance criteria:

- There is one clear owner for subprocess lifecycle and reconnection behavior.

### Phase 7: Add regression tests for the risky paths

- Add focused tests for:
  - multiple simultaneous permission prompts
  - session-bound approval reset behavior
  - critical risk rendering
  - command registry/help consistency
  - concurrent same-name tool correlation

Acceptance criteria:

- The known risk areas have direct regression coverage.

## Consequences

**Positive:**

- Correctness issues around permission handling are addressed before broader refactors.
- The TUI protocol boundary becomes easier to reason about and less likely to drift from backend behavior.
- Command and lifecycle abstractions become simpler to extend.
- Future reviews can validate against explicit acceptance criteria instead of relying on informal expectations.

**Negative:**

- The work spans UI state, protocol typing, event projection, and test infrastructure, so implementation will touch multiple modules.
- Some short-term churn is expected while duplicated abstractions are collapsed.
- Refactoring `AppShell` and command handling may require updating tests that currently rely on integrated behavior.

## Implementation Order

1. Permission correctness and focused input handling
2. Permission protocol and risk-type alignment
3. Command system unification
4. Tool/event correlation hardening
5. `AppShell` decomposition
6. Lifecycle abstraction cleanup
7. Regression test expansion and cleanup

## Related Decisions

- ADR-011: Hook / Event System
- ADR-012: Event Telemetry and Observability

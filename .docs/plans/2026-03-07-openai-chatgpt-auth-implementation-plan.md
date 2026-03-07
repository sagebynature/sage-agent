# OpenAI ChatGPT Subscription Auth for Sage

## Status

Proposed

## Date

2026-03-07

## Summary

This document defines the implementation plan for adding first-class support in
Sage for OpenAI model access authenticated through a ChatGPT subscription flow,
rather than a standard `OPENAI_API_KEY`.

The core decision is to implement this as a dedicated provider and auth stack,
not as additional LiteLLM configuration. Sage already has a stable provider
boundary, but its current default path assumes LiteLLM owns transport and auth.
That assumption does not fit the ChatGPT/Codex-style OAuth flow.

## Context

Sage currently defaults to `LiteLLMProvider` when no provider is explicitly
supplied. This happens in `sage/agent.py`, where `Agent.__init__()` constructs
`LiteLLMProvider(model, **model_params)` directly.

Relevant current seams:

- `sage/providers/base.py`
  - Defines `ProviderProtocol` with `complete()`, `stream()`, and `embed()`.
- `sage/providers/litellm_provider.py`
  - Owns the generic API-key-based provider path.
- `sage/agent.py`
  - Hardcodes the LiteLLM default provider construction.
- `sage/config.py`
  - Defines `AgentConfig`, but has no field for explicit provider selection or
    provider-specific auth configuration.
- `sage/main_config.py`
  - Defines `[defaults]` and `[agents.*]` overrides, but likewise has no
    provider field or provider-specific config.
- `sage/cli/main.py`
  - Has no auth lifecycle commands.
- `sage/models.py`
  - Message models do not carry opaque provider metadata for backend-specific
    state.

Public references informing this plan:

- OpenCode documents a user flow that connects OpenAI via ChatGPT Plus/Pro and
  stores local auth state rather than prompting for an API key.
- OpenAI’s Codex CLI documents a "sign in with ChatGPT" path in addition to
  normal API-key usage.
- Public Codex ecosystem material indicates the flow relies on browser-based
  OAuth, a localhost callback, token exchange, and a backend that is not
  identical to the standard OpenAI API path.

This plan is based on those public signals and on Sage’s current architecture.
Exact endpoint semantics must still be validated during implementation.

## Goals

- Add a supported path for using eligible OpenAI models in Sage through a
  ChatGPT subscription login flow.
- Preserve the existing LiteLLM path for standard OpenAI, Azure, Anthropic,
  Ollama, and other providers.
- Keep the agent loop, tool system, memory, and orchestration code largely
  unchanged by containing auth and transport differences inside a provider.
- Expose explicit CLI commands for login, status, and logout.
- Store credentials locally in a dedicated Sage-managed location.
- Build the feature incrementally so text completions land before streaming and
  tool calling.

## Non-Goals

- Replacing LiteLLM as Sage’s general-purpose provider layer.
- Supporting multi-user shared server auth with a single ChatGPT subscription.
- Treating ChatGPT subscription auth as a production server-side substitute for
  normal OpenAI API credentials.
- Implementing embeddings through the ChatGPT-authenticated path in the first
  release.
- Building a GUI or TUI auth wizard in the first iteration.

## Decision

Sage will add a new first-class provider family named `openai_chatgpt`.

That provider family will consist of:

1. A provider registry / factory used by `Agent` construction.
2. A dedicated auth subsystem that owns OAuth login, token refresh, token
   storage, and logout.
3. A dedicated HTTP transport implementation using `httpx`.
4. An explicit config surface for selecting the provider.
5. New CLI commands for managing authentication state.

The initial implementation will target:

1. Login and local credential storage.
2. Non-streaming chat completions.
3. Streaming chat completions.
4. Tool calling only after the provider has proven stable for text generation.

## Architecture Overview

### 1. Provider Selection

Replace the current implicit default construction with a provider factory:

- Input:
  - `model`
  - optional `provider`
  - model parameters
  - provider-specific settings
- Output:
  - object implementing `ProviderProtocol`

Rules:

- If `provider` is omitted, preserve current behavior and default to LiteLLM.
- If `provider == "litellm"`, construct `LiteLLMProvider`.
- If `provider == "openai_chatgpt"`, construct the new ChatGPT-backed provider.

This change isolates provider choice in one place and avoids scattering
conditionals across the agent runtime.

### 2. Auth Subsystem

Add a new package:

- `sage/auth/__init__.py`
- `sage/auth/openai_chatgpt.py`

Responsibilities:

- Start browser login flow.
- Generate PKCE verifier/challenge.
- Start localhost callback listener.
- Exchange auth code for access/refresh tokens.
- Persist credentials to disk.
- Refresh expired access tokens.
- Expose status and logout operations.

Proposed models:

- `OAuthTokenSet`
- `OpenAIChatGPTCredentials`
- `OpenAIChatGPTAuthManager`

Proposed storage path:

- `~/.config/sage/auth/openai-chatgpt.json`

Rationale:

- Keeps credentials under Sage’s namespace.
- Avoids coupling Sage to OpenCode’s on-disk format.
- Makes logout and migration behavior explicit.

### 3. Transport Layer

Add a dedicated provider:

- `sage/providers/openai_chatgpt_provider.py`

Responsibilities:

- Convert Sage `Message` objects into backend request payloads.
- Inject bearer tokens from the auth manager.
- Retry once on token-expiry boundaries after refresh.
- Parse non-streaming responses into `CompletionResult`.
- Parse streaming responses into `StreamChunk`.
- Normalize tool calls into Sage `ToolCall`.
- Preserve opaque provider-specific metadata for follow-up turns.

This provider should not depend on LiteLLM.

### 4. Provider Metadata Preservation

Extend the message model to support provider-scoped state:

- `sage/models.py`
  - Add `provider_metadata: dict[str, Any] | None = None` to `Message`.

Why:

- ChatGPT/Codex-style backends may require opaque turn state to be sent back on
  subsequent requests.
- The current model only retains user-visible content and tool-call data.
- Without a provider metadata channel, Sage would be forced either to drop state
  or to hide provider-specific hacks in unrelated fields.

The provider metadata must:

- survive storage in conversation history
- survive compaction where appropriate
- not be shown to the model as plain text
- be excluded from user-facing rendering unless explicitly debugged

### 5. CLI Surface

Add a new CLI group under `sage`:

- `sage auth login openai-chatgpt`
- `sage auth status openai-chatgpt`
- `sage auth logout openai-chatgpt`

Optional later commands:

- `sage auth refresh openai-chatgpt`
- `sage auth doctor openai-chatgpt`

The login command should:

1. load env and main config as usual
2. start the local callback server
3. open a browser
4. wait for completion
5. persist credentials
6. print a concise success/failure status

### 6. Config Surface

Extend both frontmatter and TOML config with explicit provider selection.

Agent frontmatter example:

```yaml
---
name: assistant
model: gpt-5-codex
provider: openai_chatgpt
---
You are a coding assistant.
```

Main config example:

```toml
[defaults]
provider = "openai_chatgpt"
model = "gpt-5-codex"
```

Provider-specific options should be added as a separate nested object, not
flattened into generic `model_params`.

Proposed shape:

```toml
[defaults.provider_options]
auth_profile = "default"
base_url = "..."
timeout = 60.0
```

Equivalent frontmatter:

```yaml
provider_options:
  auth_profile: default
  timeout: 60.0
```

This lets Sage evolve provider-specific behavior without polluting the generic
sampling config.

## Implementation Phases

### Phase 0: Discovery and Validation

Objective:

- confirm the exact request/response and auth semantics needed by the backend

Tasks:

- verify the public login flow assumptions against current OpenAI/Codex docs
- inspect whether the target backend accepts OpenAI-style tool schemas directly
- confirm whether conversation state requires opaque metadata fields
- confirm whether the backend exposes usage counters compatible with `Usage`
- determine if embeddings are unsupported or merely different

Exit criteria:

- written notes on exact HTTP paths, auth endpoints, callback URI, token shape,
  and streaming format

### Phase 1: Provider Registry and Config Plumbing

Objective:

- let Sage explicitly choose a provider family without changing runtime behavior

Files:

- `sage/config.py`
- `sage/main_config.py`
- `sage/agent.py`
- `sage/providers/__init__.py`
- new `sage/providers/factory.py`
- tests under `tests/test_config.py`, `tests/test_main_config.py`,
  `tests/test_agent.py`

Tasks:

- add `provider: str | None = None` to `AgentConfig`
- add `provider_options: dict[str, Any] | None = None` to `AgentConfig`
- add matching fields to main config override models
- implement provider factory
- replace direct `LiteLLMProvider(...)` construction in `Agent.__init__()`
- preserve default behavior when `provider` is unset

Exit criteria:

- existing configs still work unchanged
- explicit `provider = "litellm"` works
- explicit `provider = "openai_chatgpt"` resolves to a stub provider in tests

### Phase 2: Auth Models and Local Credential Store

Objective:

- create the auth substrate before wiring real network calls

Files:

- new `sage/auth/openai_chatgpt.py`
- new `tests/test_auth/test_openai_chatgpt_auth.py`

Tasks:

- define credential and token models
- implement atomic file writes for credential persistence
- implement credential load/save/delete/status helpers
- implement expiry calculation helpers
- define refresh contract, even if refresh is mocked first

Requirements:

- never log secrets
- reject malformed credential files with a clear error
- support future profile selection if multiple auth profiles are added

Exit criteria:

- credential round-trip tests pass
- expired-token and malformed-file cases are covered

### Phase 3: CLI Auth Commands

Objective:

- expose authentication lifecycle to users before provider calls depend on it

Files:

- `sage/cli/main.py`
- new tests in `tests/test_cli/`

Tasks:

- add `auth` command group
- add `login`, `status`, `logout` subcommands for `openai-chatgpt`
- wire command output for success, unauthenticated, expired, and revoked states
- return correct exit codes for auth failures

Exit criteria:

- users can run auth commands without touching agent runtime
- login workflow can be stubbed in tests

### Phase 4: Browser OAuth Login

Objective:

- implement end-to-end login and refresh token acquisition

Files:

- `sage/auth/openai_chatgpt.py`
- possibly new helpers:
  - `sage/auth/oauth.py`
  - `sage/auth/callback_server.py`

Tasks:

- generate PKCE code verifier / challenge
- start localhost callback listener on an available port
- construct auth URL
- open browser using the system default browser
- receive auth code
- exchange auth code for token set
- persist resulting credentials

Behavioral requirements:

- time out cleanly if the user never completes login
- print the callback URL if browser launch fails
- handle port collisions by retrying another port
- avoid leaving a listener process running after cancellation

Exit criteria:

- successful manual login on a developer machine
- callback timeout and browser-launch failure paths tested

### Phase 5: Minimal ChatGPT Provider for Non-Streaming Text

Objective:

- prove that Sage can complete turns through the new provider with no agent-loop
  changes beyond provider selection

Files:

- `sage/providers/openai_chatgpt_provider.py`
- `sage/models.py`
- `tests/test_providers/test_openai_chatgpt_provider.py`

Tasks:

- map Sage messages into backend format
- load credentials via auth manager
- attach bearer token
- send non-streaming request with `httpx`
- parse assistant content into `CompletionResult`
- map usage fields where available
- store any opaque backend turn metadata in `Message.provider_metadata`

Behavioral requirements:

- refresh and retry once on token expiry
- raise `ProviderError` on auth or transport failures
- avoid breaking compaction or memory code that consumes `Message`

Exit criteria:

- text-only round-trip tests pass
- one manual prompt works through `sage agent run`

### Phase 6: Streaming Support

Objective:

- support Sage’s existing streaming execution path

Files:

- `sage/providers/openai_chatgpt_provider.py`
- `tests/test_providers/test_openai_chatgpt_provider.py`

Tasks:

- parse SSE or chunked response protocol
- emit `StreamChunk(delta=...)` for text segments
- emit terminal chunk with `finish_reason`
- attach usage if the backend exposes it at the end of stream
- preserve provider metadata needed for the next turn

Exit criteria:

- `sage agent run --stream` works with the new provider
- stream interruption and malformed-event cases are tested

### Phase 7: Tool Calling

Objective:

- support Sage tools through the new provider path

Files:

- `sage/providers/openai_chatgpt_provider.py`
- `sage/tools/dispatcher.py` only if provider differences require it
- tests under `tests/test_providers/` and `tests/test_agent/`

Tasks:

- confirm backend tool schema format
- serialize Sage `ToolSchema` into backend function format
- parse tool calls into `ToolCall`
- preserve tool call IDs and argument reconstruction
- validate behavior in both non-stream and stream modes

Special attention:

- some backends stream tool-call fragments incrementally
- some backends require full message history on every turn
- some backends reject fields tolerated by the standard OpenAI API

Exit criteria:

- a simple built-in tool call completes end-to-end
- existing agent loop executes the tool and continues normally

### Phase 8: Hardening and Documentation

Objective:

- make the feature supportable for normal users

Files:

- `README.md`
- `.docs/agent-authoring.md`
- new provider auth docs under `.docs/`
- changelog entry if appropriate

Tasks:

- document setup and limitations
- add troubleshooting guidance
- add logging redaction checks
- add revocation / invalid session recovery guidance
- document when users should prefer API keys instead

Exit criteria:

- docs are sufficient for a new user to authenticate and run one agent

## Detailed File Plan

### New Files

- `.docs/plans/2026-03-07-openai-chatgpt-auth-implementation-plan.md`
- `sage/providers/factory.py`
- `sage/providers/openai_chatgpt_provider.py`
- `sage/auth/__init__.py`
- `sage/auth/openai_chatgpt.py`
- optional:
  - `sage/auth/oauth.py`
  - `sage/auth/callback_server.py`
- tests:
  - `tests/test_auth/test_openai_chatgpt_auth.py`
  - `tests/test_providers/test_openai_chatgpt_provider.py`

### Existing Files to Modify

- `sage/agent.py`
  - replace default provider construction with factory lookup
- `sage/config.py`
  - add provider-related config fields
- `sage/main_config.py`
  - add provider-related override fields
- `sage/providers/__init__.py`
  - export the new provider and factory
- `sage/models.py`
  - add provider metadata support to `Message`
- `sage/cli/main.py`
  - add auth subcommands
- `README.md`
  - document provider selection and auth commands

## Testing Strategy

### Unit Tests

- provider factory chooses the correct provider class
- config parsing accepts and merges `provider` / `provider_options`
- credential storage round-trips cleanly
- expired and malformed credential states are surfaced correctly
- provider maps response payloads into `Message`, `ToolCall`, and `Usage`
- streaming parser emits correct chunk sequence

### Integration Tests

- `sage auth status openai-chatgpt` reflects saved credential state
- `sage agent run` can use an injected fake transport for `openai_chatgpt`
- tool-calling round-trip works using a mocked backend

### Manual Validation

- log in successfully on macOS/Linux
- run a plain prompt
- run a streamed prompt
- run a prompt that invokes a simple tool
- invalidate tokens and confirm refresh or re-auth behavior

### Regression Checks

- ensure all existing LiteLLM tests still pass
- ensure config parsing remains backward-compatible
- ensure compaction and memory logic tolerate `provider_metadata`

## Risks and Mitigations

### Risk 1: Backend Semantics Diverge from Standard OpenAI API

Impact:

- message conversion and tool calling may not match existing assumptions

Mitigation:

- implement as a dedicated provider
- stage delivery: text first, tools later
- isolate payload translation in one module

### Risk 2: Auth Flow Changes Upstream

Impact:

- browser login or token refresh could break without code changes in Sage

Mitigation:

- keep auth logic self-contained
- add clear diagnostics for auth failures
- document that this provider depends on upstream ChatGPT/Codex login behavior

### Risk 3: Opaque Conversation State Is Required

Impact:

- responses may degrade or fail across turns if hidden metadata is dropped

Mitigation:

- add provider metadata support at the model layer before implementing the
  provider
- verify multi-turn behavior early in Phase 5

### Risk 4: Security Mistakes in Credential Handling

Impact:

- accidental credential leakage in logs or traces

Mitigation:

- never log raw tokens
- centralize credential serialization
- add explicit tests for redaction-sensitive paths

### Risk 5: Misuse for Headless Production Workloads

Impact:

- users may rely on a consumer login flow in contexts where API keys are the
  correct solution

Mitigation:

- document intended usage clearly
- keep API-key-based OpenAI support as the recommended production path

## Open Questions

- What exact backend endpoint and request shape should Sage target for
  non-streaming completions as of March 7, 2026?
- What exact streaming protocol is returned?
- Are tool schemas identical to OpenAI function calling, or only similar?
- Does the backend require full conversation replay every turn?
- Which response fields must be preserved as `provider_metadata`?
- Is usage returned in a form that maps cleanly into Sage’s `Usage` model?
- Are there model naming differences between user-facing names and backend
  request identifiers?
- Should provider auth state support multiple named profiles in v1, or only a
  single default profile?

## Rollout Recommendation

Recommended implementation order:

1. Phase 1: provider registry and config plumbing
2. Phase 2: auth storage models
3. Phase 3: auth CLI commands
4. Phase 4: browser login flow
5. Phase 5: non-streaming text provider
6. Phase 6: streaming provider
7. Phase 7: tool calling
8. Phase 8: docs and hardening

This order lets the team land reversible infrastructure first and postpone the
highest-uncertainty pieces until the auth and provider seams are stable.

## Success Criteria

The feature is considered complete when all of the following are true:

- a user can run `sage auth login openai-chatgpt`
- Sage stores and reuses credentials locally
- an agent configured with `provider: openai_chatgpt` can complete a normal
  prompt
- streaming works
- at least one built-in tool works end-to-end through the provider
- the existing LiteLLM path remains backward-compatible
- docs explain setup, limits, and failure recovery

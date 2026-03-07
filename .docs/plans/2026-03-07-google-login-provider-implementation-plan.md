# Google Login Provider for Sage

## Status

Proposed

## Date

2026-03-07

## Summary

This document defines the implementation plan for adding Google-login-backed
model access to Sage.

The feature should support authenticating with a Google account through a
browser OAuth flow, then using the resulting session for Google-backed models in
Sage without requiring a `GEMINI_API_KEY` or other static API key.

This plan explicitly separates two targets:

1. An official Google login path aligned with Gemini CLI / Gemini Code Assist.
2. An optional experimental Antigravity-style bridge inspired by
   `opencode-antigravity-auth`.

The recommendation is to implement the official Google login path first and
defer any Antigravity-compatible bridge until the provider and auth foundation
is stable.

## Context

Sage already has a provider boundary, but it currently assumes LiteLLM owns
transport and authentication for most providers.

Relevant current seams:

- `sage/providers/base.py`
  - defines `ProviderProtocol`
- `sage/providers/litellm_provider.py`
  - handles the generic API-key-based route
- `sage/agent.py`
  - currently defaults to `LiteLLMProvider(...)`
- `sage/config.py`
  - has no explicit provider field or provider-specific auth config
- `sage/main_config.py`
  - has no provider-specific override support
- `sage/cli/main.py`
  - has no auth login / status / logout commands
- `sage/models.py`
  - has no dedicated channel for provider-specific opaque state

External references informing this plan:

- Official Gemini CLI documentation describes a `Login with Google` flow using
  a Google account, with no API key management required.
- Official Gemini CLI docs indicate `GOOGLE_CLOUD_PROJECT` may be required for
  some paid Code Assist or organization-backed use cases.
- The referenced `opencode-antigravity-auth` plugin shows a different pattern:
  intercept requests, authenticate via Google OAuth, transform payloads, and
  send them to Antigravity / Google gateway endpoints.
- That plugin explicitly warns that using the Antigravity proxy path may
  violate Google’s Terms of Service and may result in account restrictions.

This distinction matters. "Google login" and "Antigravity compatibility" are
related, but they should not be treated as the same feature inside Sage.

## Sources

Official Google sources:

- Gemini CLI GitHub README: `Login with Google` auth option, free tier and
  `GOOGLE_CLOUD_PROJECT` note
  - https://github.com/google-gemini/gemini-cli
- Google Cloud Gemini CLI documentation
  - https://cloud.google.com/gemini/docs/codeassist/gemini-cli

Reference implementation / inspiration:

- Antigravity plugin README
  - https://github.com/NoeFabris/opencode-antigravity-auth
- Antigravity plugin architecture document
  - https://github.com/NoeFabris/opencode-antigravity-auth/blob/main/docs/ARCHITECTURE.md

## Goals

- Add first-class Google account login support to Sage.
- Allow a Sage agent to use Google-backed models after browser login.
- Avoid static key management for individual users where Google login is
  supported.
- Preserve backward compatibility with existing LiteLLM and API-key flows.
- Create an explicit CLI auth lifecycle.
- Keep the official Google login path separate from any experimental
  Antigravity-style compatibility layer.

## Non-Goals

- Replacing LiteLLM for general Gemini API-key usage.
- Supporting every Google-authenticated ecosystem path in v1.
- Delivering Antigravity compatibility in the first implementation phase.
- Treating consumer login-backed flows as the default for server-side or
  production multi-user workloads.
- Supporting multi-account rotation in the first release.

## Decision

Sage should implement a new provider family for Google login-backed access with
two layers:

1. `google_login`
   - official, preferred, lower-risk target
   - based on Google account browser login semantics similar to Gemini CLI
2. `google_antigravity`
   - optional, experimental, higher-risk target
   - based on Google OAuth plus request transformation to Antigravity-like
     endpoints

The first deliverable should only target `google_login`.

Antigravity compatibility should be intentionally delayed and clearly labeled as
experimental because:

- it relies on less stable and less official semantics
- it may require heavier payload transformation
- the public reference plugin warns about Terms of Service risk
- it increases maintenance cost substantially

## Recommended Product Positioning

Inside Sage, these should be presented as distinct choices:

- `provider: google_login`
  - recommended for normal users
  - official Google-login-backed provider path
- `provider: google_antigravity`
  - experimental / unsupported by default
  - disabled unless explicitly configured

This prevents users from assuming that all Google-backed login modes have the
same support level or policy risk.

## Architecture Overview

### 1. Provider Selection

Add explicit provider selection to agent config and main config.

Required provider values:

- `litellm`
- `openai_chatgpt`
- `google_login`

Optional future provider:

- `google_antigravity`

This requires a provider factory so `Agent` no longer constructs LiteLLM
directly.

### 2. Shared Auth Framework

The OpenAI ChatGPT work already justifies a generic auth subsystem. Google login
should reuse the same framework shape.

Recommended package structure:

- `sage/auth/__init__.py`
- `sage/auth/base.py`
- `sage/auth/openai_chatgpt.py`
- `sage/auth/google_login.py`

Shared responsibilities:

- browser launch
- localhost callback handling
- token storage
- token refresh
- status / logout
- secret-safe logging

Provider-specific responsibilities:

- auth URL construction
- token exchange details
- refresh semantics
- required scopes
- account metadata parsing

### 3. Official Google Login Provider

Add:

- `sage/providers/google_login_provider.py`

Responsibilities:

- load Google login credentials from the auth manager
- map Sage messages into the target Google-backed request format
- attach access tokens
- refresh on expiry
- parse responses into `CompletionResult`
- support streaming
- support tool calling only after the text path is proven
- preserve provider metadata when the backend requires it

This provider should use `httpx` directly, not LiteLLM.

### 4. Experimental Antigravity Provider

Add later:

- `sage/providers/google_antigravity_provider.py`

Responsibilities:

- authenticate via Google OAuth
- transform Sage messages and tool schemas to the target Antigravity/Gemini
  payload format
- normalize model naming
- handle special schema restrictions
- preserve opaque turn metadata if required

This provider should be implemented only after:

- the shared Google auth manager exists
- the official provider is working
- the request transformation requirements are validated

### 5. Provider Metadata Preservation

Google-backed providers may require extra opaque state between turns.

Add to `sage/models.py`:

- `provider_metadata: dict[str, Any] | None = None` on `Message`

Requirements:

- keep provider metadata out of normal prompt text
- retain it in conversation history
- avoid breaking compaction and memory logic
- avoid rendering it in user-facing output except in debug tooling

### 6. CLI Surface

Add a top-level auth command group:

- `sage auth login google`
- `sage auth status google`
- `sage auth logout google`

Optional future commands:

- `sage auth doctor google`
- `sage auth refresh google`

If Antigravity support is later added, it should be surfaced separately:

- `sage auth login google-antigravity`
- `sage auth status google-antigravity`

This keeps the user-facing model honest.

## Config Surface

Recommended agent frontmatter:

```yaml
---
name: assistant
model: gemini-2.5-pro
provider: google_login
provider_options:
  auth_profile: default
  google_cloud_project: my-project-id
---
You are a coding assistant.
```

Recommended main config:

```toml
[defaults]
provider = "google_login"
model = "gemini-2.5-pro"

[defaults.provider_options]
auth_profile = "default"
google_cloud_project = "my-project-id"
```

Potential provider-specific options:

- `auth_profile`
- `google_cloud_project`
- `base_url`
- `timeout`
- `experimental_features`

For the experimental Antigravity provider, additional options would likely be
needed, such as:

- `mode = "antigravity"`
- `quota_strategy`
- `grounding_mode`
- `enable_thinking`

Those options should not pollute the official `google_login` path.

## Model Strategy

For `google_login`, model naming should stay close to official Google model
identifiers where possible.

Examples:

- `gemini-2.5-flash`
- `gemini-2.5-pro`
- future official Google-backed model strings as supported

For `google_antigravity`, model naming should be explicitly namespaced to avoid
confusion:

- `google/antigravity-gemini-3-pro`
- `google/antigravity-claude-opus-*`

Do not overload the same model names for both providers.

## Implementation Phases

### Phase 0: Discovery and Validation

Objective:

- confirm the exact official Google login-backed transport Sage should target

Tasks:

- verify current official Google login flow and callback expectations
- identify the backend endpoint family used after Google login
- determine token scopes and refresh behavior
- confirm whether `GOOGLE_CLOUD_PROJECT` is optional, recommended, or required
  for different account types
- determine whether official Google login supports the same tool-call structure
  Sage expects
- verify whether the backend uses OpenAI-style messages or a different format

For Antigravity follow-up discovery:

- identify request / response transformations required
- identify schema restrictions and unsupported fields
- identify whether model normalization is required

Exit criteria:

- documented notes on official Google login transport and auth semantics
- documented notes on Antigravity-specific differences

### Phase 1: Provider Registry and Config Plumbing

Objective:

- support explicit provider selection for Google-backed providers

Files:

- `sage/config.py`
- `sage/main_config.py`
- `sage/agent.py`
- new `sage/providers/factory.py`
- `sage/providers/__init__.py`

Tasks:

- add `provider` to `AgentConfig`
- add `provider_options` to `AgentConfig`
- add matching fields to main config overrides
- implement provider factory
- preserve current LiteLLM default behavior when provider is omitted

Exit criteria:

- `provider: google_login` resolves to a stub provider in tests
- existing configs remain backward-compatible

### Phase 2: Google Auth Manager and Credential Storage

Objective:

- implement auth lifecycle independently of inference calls

Files:

- `sage/auth/base.py`
- `sage/auth/google_login.py`
- tests under `tests/test_auth/`

Suggested models:

- `OAuthTokenSet`
- `GoogleLoginCredentials`
- `GoogleLoginAccount`
- `GoogleLoginAuthManager`

Suggested storage path:

- `~/.config/sage/auth/google-login.json`

Tasks:

- add credential serialization
- implement atomic writes
- implement load/save/delete/status helpers
- model expiry and refresh windows
- include account identity metadata if available
- support optional `google_cloud_project`

Exit criteria:

- credential round-trip tests pass
- malformed and expired states are handled correctly

### Phase 3: CLI Auth Commands

Objective:

- expose Google auth lifecycle before provider calls depend on it

Files:

- `sage/cli/main.py`
- tests in `tests/test_cli/`

Tasks:

- add `sage auth login google`
- add `sage auth status google`
- add `sage auth logout google`
- wire success and failure output
- choose exit code behavior for auth failures

Exit criteria:

- auth commands work with mocked auth manager

### Phase 4: Browser OAuth Login Flow

Objective:

- implement real Google browser login

Files:

- `sage/auth/google_login.py`
- optional helpers:
  - `sage/auth/oauth.py`
  - `sage/auth/callback_server.py`

Tasks:

- generate auth URL
- start callback listener on localhost
- open system browser
- receive callback
- exchange code for tokens
- persist credentials

Behavioral requirements:

- clean timeout handling
- clear fallback if browser open fails
- port collision handling
- safe shutdown on interruption

Exit criteria:

- manual login works on a developer machine
- timeout and callback failure cases are tested

### Phase 5: Official Google Login Provider for Text Completions

Objective:

- get a basic Sage turn working through Google login-backed access

Files:

- `sage/providers/google_login_provider.py`
- `sage/models.py`
- `tests/test_providers/test_google_login_provider.py`

Tasks:

- map Sage messages into backend payload
- attach tokens
- refresh and retry once on expiry
- parse text response into `CompletionResult`
- map usage when available
- persist provider metadata if needed

Exit criteria:

- text-only prompt completes through `sage agent run`
- unit tests cover auth failure and transport failure cases

### Phase 6: Streaming Support

Objective:

- support `sage agent run --stream` through the official Google provider

Files:

- `sage/providers/google_login_provider.py`
- tests in `tests/test_providers/`

Tasks:

- parse streaming protocol
- emit `StreamChunk` deltas
- propagate finish reason
- propagate final usage if available

Exit criteria:

- streaming round-trip works in tests and manual validation

### Phase 7: Tool Calling

Objective:

- support Sage built-in tools through the official Google provider

Files:

- `sage/providers/google_login_provider.py`
- maybe `sage/tools/dispatcher.py`
- tests in `tests/test_providers/` and `tests/test_agent/`

Tasks:

- map `ToolSchema` into the backend format
- normalize returned tool calls into `ToolCall`
- preserve tool call IDs and argument JSON
- validate stream and non-stream tool calling

Exit criteria:

- at least one built-in tool works end-to-end

### Phase 8: Experimental Antigravity Provider Discovery

Objective:

- only after the official provider works, define the exact Antigravity delta

Tasks:

- identify transformation logic needed beyond the official provider
- identify schema cleaning rules
- identify model name translation
- identify whether special reasoning / thinking handling is required
- define Terms-of-Service warning behavior in docs and CLI

Exit criteria:

- separate design note for `google_antigravity`

### Phase 9: Experimental Antigravity Implementation

Objective:

- optional and gated implementation of the Antigravity-compatible provider

Files:

- `sage/providers/google_antigravity_provider.py`
- `sage/auth/google_antigravity.py` if auth diverges materially
- dedicated tests
- dedicated docs

Tasks:

- implement request transformation
- implement response transformation
- handle schema restrictions
- handle special reasoning / signature state if required
- document quota and policy caveats

Exit criteria:

- explicitly marked experimental
- separated from the official provider in config, docs, and CLI

## Detailed File Plan

### New Files

- `.docs/plans/2026-03-07-google-login-provider-implementation-plan.md`
- `sage/providers/factory.py`
- `sage/providers/google_login_provider.py`
- `sage/auth/base.py`
- `sage/auth/google_login.py`
- future optional:
  - `sage/providers/google_antigravity_provider.py`
  - `sage/auth/google_antigravity.py`

### Existing Files to Modify

- `sage/agent.py`
  - use provider factory
- `sage/config.py`
  - add provider and provider options
- `sage/main_config.py`
  - add provider override fields
- `sage/providers/__init__.py`
  - export new providers / factory
- `sage/models.py`
  - add provider metadata support
- `sage/cli/main.py`
  - add auth CLI commands
- `README.md`
  - document Google login setup and limitations

## Testing Strategy

### Unit Tests

- config parsing for `provider: google_login`
- config merge behavior from TOML and frontmatter
- auth credential store round-trip
- provider request mapping
- provider response mapping
- streaming chunk parsing
- tool-call parsing

### Integration Tests

- `sage auth status google` reflects stored credentials
- `sage agent run` works with a mocked Google-login-backed transport
- tool-calling works through mocked provider responses

### Manual Validation

- log in with a Google account
- run a plain text prompt
- run a streaming prompt
- run a prompt that invokes a built-in tool
- validate optional `GOOGLE_CLOUD_PROJECT` behavior where relevant

### Regression Checks

- existing LiteLLM tests still pass
- OpenAI ChatGPT auth path remains unaffected
- memory and compaction tolerate provider metadata

## Risks and Mitigations

### Risk 1: Official Google Login Transport Is Not Stable or Public Enough

Impact:

- implementation details may drift or be hard to maintain

Mitigation:

- perform discovery first
- encapsulate auth and transport in one provider
- keep API-key Gemini support as the stable fallback

### Risk 2: Official and Antigravity Paths Get Conflated

Impact:

- confusing UX, unclear support expectations, hidden policy risk

Mitigation:

- separate providers and config names
- separate docs
- explicit experimental label for Antigravity

### Risk 3: Terms-of-Service / Account Safety Risk for Antigravity

Impact:

- potential account restrictions for users

Mitigation:

- do not make Antigravity the default plan
- document the warning explicitly if ever implemented
- keep official Google login as the recommended path

### Risk 4: `GOOGLE_CLOUD_PROJECT` Semantics Vary by Account Type

Impact:

- confusing auth failures for organization-backed or paid flows

Mitigation:

- expose `google_cloud_project` as provider option
- document when it is needed
- include targeted diagnostics in auth status / doctor commands

### Risk 5: Backend Uses Different Tool Schema Semantics

Impact:

- Sage tool calling may need a provider-specific adapter

Mitigation:

- ship text completions first
- implement tool calling only after exact format validation

## Open Questions

- What exact backend should the official `google_login` provider target after
  browser login?
- Are the post-login requests made to Gemini CLI / Code Assist endpoints,
  Google GenAI endpoints, or another internal service boundary?
- What scopes and token fields are required?
- Is `GOOGLE_CLOUD_PROJECT` only for organization-backed accounts, or can it
  affect consumer flows too?
- Does the official Google-login-backed transport support tool calling in a way
  that maps cleanly to Sage’s agent loop?
- What provider metadata, if any, must be preserved across turns?
- If Antigravity support is added later, what exact ToS and account-safety
  warnings should Sage present?

## Rollout Recommendation

Recommended order:

1. Provider registry and config plumbing
2. Shared auth framework
3. Google auth manager and CLI commands
4. Official Google login provider for text completions
5. Streaming support
6. Tool calling
7. Documentation and hardening
8. Separate discovery for Antigravity
9. Optional experimental Antigravity provider

This ordering keeps the lower-risk, more supportable path first.

## Success Criteria

The feature is considered complete for the official path when:

- a user can run `sage auth login google`
- Sage stores and reuses Google login credentials locally
- an agent configured with `provider: google_login` can answer a normal prompt
- streaming works
- at least one built-in tool works end-to-end
- the existing LiteLLM and OpenAI ChatGPT paths are not regressed
- docs clearly explain when to use Google login vs API keys

Antigravity support, if implemented later, should be considered a separate
success milestone rather than part of the base Google-login feature.

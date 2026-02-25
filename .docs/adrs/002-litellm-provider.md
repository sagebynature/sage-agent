# ADR-002: LiteLLM as Provider Layer

## Status
Accepted

## Context
The SDK needs a unified API to interact with 100+ LLM providers (OpenAI, Azure AI Foundry, Anthropic, Ollama, etc.) without writing and maintaining individual provider integrations. Building custom provider adapters for each service would be a significant ongoing maintenance burden.

## Decision
Use [litellm](https://github.com/BerriAI/litellm) as the underlying provider abstraction layer. All LLM calls route through litellm's `acompletion` and `aembedding` APIs, wrapped behind our `ProviderProtocol` interface.

Model strings follow litellm conventions (e.g., `gpt-4o`, `anthropic/claude-sonnet-4-20250514`, `azure/gpt-4o`, `ollama/llama3`).

## Consequences
**Positive:**
- Instant support for 100+ providers with a single dependency
- Battle-tested and community-maintained
- Consistent tool-calling interface across providers
- Handles provider-specific quirks (auth, retry, rate limiting)
- Users can switch providers by changing one model string

**Negative:**
- Adds a transitive dependency tree (httpx, tiktoken, etc.)
- Version updates may introduce breaking changes in provider behavior
- Less control over low-level request/response handling
- Must track litellm releases for new provider support

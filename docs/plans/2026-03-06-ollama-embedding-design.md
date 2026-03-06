# Ollama Embedding Support Design

**Date:** 2026-03-06
**Status:** Approved

## Summary

Add first-class Ollama embedding support via a new `OllamaEmbedding` class that calls Ollama's HTTP API directly (no LiteLLM). A `create_embedding()` factory function routes to the right implementation based on a prefix convention (`ollama/model-name`).

## Architecture

### New: `OllamaEmbedding` (`sage/memory/embedding.py`)

A class satisfying `EmbeddingProtocol` that calls Ollama's `POST /api/embed` endpoint via `httpx.AsyncClient`.

- Reads `OLLAMA_API_BASE` from the environment; defaults to `http://localhost:11434`
- Constructor: `OllamaEmbedding(model: str, base_url: str)`
- `async def embed(self, texts: list[str]) -> list[list[float]]`

### New: `create_embedding(model_str: str) -> EmbeddingProtocol` (`sage/memory/embedding.py`)

Factory function that parses the model string prefix:

| Prefix    | Returns               |
|-----------|-----------------------|
| `ollama/` | `OllamaEmbedding`     |
| anything else | `LiteLLMEmbedding` |

Raises `ValueError` immediately if `"ollama/"` is present but no model name follows.

### Changed: `_build_memory_backend` (`sage/agent.py`)

One-line change — replaces direct `LiteLLMEmbedding` construction with `create_embedding()`:

```python
# before
embedding = LiteLLMEmbedding(agent_config.memory.embedding)

# after
from sage.memory.embedding import create_embedding
embedding = create_embedding(agent_config.memory.embedding)
```

### Configuration

`MemoryConfig.embedding` remains a plain string. No schema changes.

```toml
# config.toml
[memory]
embedding = "ollama/nomic-embed-text"
```

```yaml
# agent frontmatter
memory:
  embedding: "ollama/nomic-embed-text"
```

Environment variable: `OLLAMA_API_BASE` (optional, defaults to `http://localhost:11434`).

## Error Handling

| Scenario | Behaviour |
|---|---|
| Ollama not running / wrong URL | `ProviderError` wrapping `httpx.ConnectError`, message includes base URL and `OLLAMA_API_BASE` hint |
| Non-200 HTTP response | `ProviderError` with HTTP status and response body |
| `"ollama/"` with no model name | `ValueError` raised at construction time in `create_embedding()` |

## Testing

New tests in `tests/test_memory/test_embedding.py`:

- `test_ollama_embedding_success` — mock `httpx.AsyncClient.post`, assert correct vectors returned
- `test_ollama_embedding_connection_error` — mock `httpx.ConnectError`, assert `ProviderError` raised
- `test_create_embedding_routing` — assert factory returns correct types for `"ollama/..."` and plain model strings

No new dependencies (`httpx` is already a transitive dependency via LiteLLM).

# Ollama Embedding Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a first-class `OllamaEmbedding` class and `create_embedding()` factory so users can set `embedding = "ollama/nomic-embed-text"` in config and get direct Ollama HTTP calls (no LiteLLM).

**Architecture:** A new `OllamaEmbedding` class in `sage/memory/embedding.py` calls `POST /api/embed` via `httpx.AsyncClient`. A new `create_embedding(model_str)` factory parses the `"ollama/"` prefix to route to `OllamaEmbedding`; all other strings go to `LiteLLMEmbedding` as before. `_build_memory_backend` in `agent.py` is updated to call the factory instead of constructing `LiteLLMEmbedding` directly.

**Tech Stack:** Python 3.12+, `httpx` (already a transitive dep via LiteLLM), `pytest-asyncio`, `unittest.mock`

---

### Task 1: OllamaEmbedding class (TDD)

**Files:**
- Modify: `sage/memory/embedding.py`
- Modify: `tests/test_memory/test_embedding.py`

---

**Step 1: Write the failing tests**

Add a new `TestOllamaEmbedding` class at the bottom of `tests/test_memory/test_embedding.py`.

First, update the imports at the top of the test file — add `httpx` and the new symbols (they don't exist yet, which is fine; the import will fail and that's the expected red state):

```python
import httpx
import pytest

from sage.exceptions import ProviderError
from sage.memory.embedding import (
    EmbeddingProtocol,
    LiteLLMEmbedding,
    OllamaEmbedding,       # does not exist yet
    ProviderEmbedding,
)
```

Then append the test class:

```python
# ---------------------------------------------------------------------------
# OllamaEmbedding
# ---------------------------------------------------------------------------


class TestOllamaEmbedding:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

        with patch("sage.memory.embedding.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = fake_response

            emb = OllamaEmbedding("nomic-embed-text", base_url="http://localhost:11434")
            result = await emb.embed(["hello", "world"])

        mock_client.post.assert_awaited_once_with(
            "http://localhost:11434/api/embed",
            json={"model": "nomic-embed-text", "input": ["hello", "world"]},
        )
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    @pytest.mark.asyncio
    async def test_connection_error(self) -> None:
        with patch("sage.memory.embedding.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.ConnectError("refused")

            emb = OllamaEmbedding("nomic-embed-text", base_url="http://localhost:11434")
            with pytest.raises(ProviderError, match="Cannot connect to Ollama"):
                await emb.embed(["hello"])

    @pytest.mark.asyncio
    async def test_non_200_response(self) -> None:
        fake_response = MagicMock()
        fake_response.status_code = 404
        fake_response.text = "model not found"

        with patch("sage.memory.embedding.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = fake_response

            emb = OllamaEmbedding("nomic-embed-text", base_url="http://localhost:11434")
            with pytest.raises(ProviderError, match="HTTP 404"):
                await emb.embed(["hello"])

    def test_satisfies_embedding_protocol(self) -> None:
        emb = OllamaEmbedding("nomic-embed-text")
        assert isinstance(emb, EmbeddingProtocol)

    def test_env_var_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_API_BASE", "http://gpu-box:11434")
        emb = OllamaEmbedding("nomic-embed-text")
        assert emb._base_url == "http://gpu-box:11434"

    def test_default_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OLLAMA_API_BASE", raising=False)
        emb = OllamaEmbedding("nomic-embed-text")
        assert emb._base_url == "http://localhost:11434"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_memory/test_embedding.py::TestOllamaEmbedding -v
```

Expected: `ImportError: cannot import name 'OllamaEmbedding'`

---

**Step 3: Implement `OllamaEmbedding`**

Add the following to `sage/memory/embedding.py`. Insert after the existing imports block (add `import os` and `import httpx`) and add the class after `LiteLLMEmbedding`:

New imports to add at the top of `sage/memory/embedding.py`:

```python
import os

import httpx
```

Import to add for `ProviderError`:

```python
from sage.exceptions import ProviderError
```

New class to append after `LiteLLMEmbedding`:

```python
class OllamaEmbedding:
    """Embed via Ollama's HTTP API directly (no LiteLLM).

    Reads ``OLLAMA_API_BASE`` from the environment; defaults to
    ``http://localhost:11434``.  The ``base_url`` constructor argument
    takes precedence over the env var::

        emb = OllamaEmbedding("nomic-embed-text")
        emb = OllamaEmbedding("nomic-embed-text", base_url="http://gpu-box:11434")
    """

    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(self, model: str, base_url: str | None = None) -> None:
        self._model = model
        self._base_url = (
            base_url
            or os.environ.get("OLLAMA_API_BASE")
            or self.DEFAULT_BASE_URL
        ).rstrip("/")
        logger.debug(
            "OllamaEmbedding initialized: model=%s, base_url=%s",
            self._model,
            self._base_url,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via ``POST /api/embed``."""
        logger.debug(
            "Embedding %d text(s) via Ollama model=%s", len(texts), self._model
        )
        url = f"{self._base_url}/api/embed"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, json={"model": self._model, "input": texts}
                )
        except httpx.ConnectError as exc:
            raise ProviderError(
                f"Cannot connect to Ollama at {self._base_url}. "
                f"Is Ollama running? Set OLLAMA_API_BASE to override."
            ) from exc
        if response.status_code != 200:
            raise ProviderError(
                f"Ollama /api/embed returned HTTP {response.status_code}: {response.text}"
            )
        data = response.json()
        return data["embeddings"]
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_memory/test_embedding.py::TestOllamaEmbedding -v
```

Expected: 6 tests PASS.

**Step 5: Commit**

```bash
git add sage/memory/embedding.py tests/test_memory/test_embedding.py
git commit -m "feat(memory): add OllamaEmbedding with direct HTTP client"
```

---

### Task 2: `create_embedding()` factory (TDD)

**Files:**
- Modify: `sage/memory/embedding.py`
- Modify: `tests/test_memory/test_embedding.py`

---

**Step 1: Write the failing tests**

Append a new `TestCreateEmbedding` class to `tests/test_memory/test_embedding.py`. Also add `create_embedding` to the import at the top of the file:

```python
from sage.memory.embedding import (
    EmbeddingProtocol,
    LiteLLMEmbedding,
    OllamaEmbedding,
    ProviderEmbedding,
    create_embedding,      # does not exist yet
)
```

Test class to append:

```python
# ---------------------------------------------------------------------------
# create_embedding factory
# ---------------------------------------------------------------------------


class TestCreateEmbedding:
    def test_routes_ollama_prefix(self) -> None:
        emb = create_embedding("ollama/nomic-embed-text")
        assert isinstance(emb, OllamaEmbedding)

    def test_routes_plain_model_to_litellm(self) -> None:
        emb = create_embedding("text-embedding-3-large")
        assert isinstance(emb, LiteLLMEmbedding)

    def test_other_prefix_goes_to_litellm(self) -> None:
        # azure/, cohere/, etc. all go to LiteLLM
        emb = create_embedding("azure/my-deployment")
        assert isinstance(emb, LiteLLMEmbedding)

    def test_empty_model_after_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="requires a model name"):
            create_embedding("ollama/")
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_memory/test_embedding.py::TestCreateEmbedding -v
```

Expected: `ImportError: cannot import name 'create_embedding'`

---

**Step 3: Implement `create_embedding()`**

Append the factory function at the end of `sage/memory/embedding.py`:

```python
def create_embedding(model_str: str) -> EmbeddingProtocol:
    """Return an :class:`EmbeddingProtocol` for *model_str*.

    Prefix routing:

    * ``"ollama/<model>"``  →  :class:`OllamaEmbedding`
    * anything else         →  :class:`LiteLLMEmbedding`

    Raises :class:`ValueError` if the ``ollama/`` prefix is present but
    no model name follows.
    """
    if model_str.startswith("ollama/"):
        model = model_str[len("ollama/"):]
        if not model:
            raise ValueError(
                "ollama/ prefix requires a model name, e.g. 'ollama/nomic-embed-text'"
            )
        return OllamaEmbedding(model)
    return LiteLLMEmbedding(model_str)
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_memory/test_embedding.py::TestCreateEmbedding -v
```

Expected: 4 tests PASS. Run the full embedding suite to check no regressions:

```bash
pytest tests/test_memory/test_embedding.py -v
```

Expected: all tests PASS.

**Step 5: Commit**

```bash
git add sage/memory/embedding.py tests/test_memory/test_embedding.py
git commit -m "feat(memory): add create_embedding() factory with ollama/ prefix routing"
```

---

### Task 3: Wire `agent.py` and update `__init__.py` exports

**Files:**
- Modify: `sage/agent.py:87-96`
- Modify: `sage/memory/__init__.py`

---

**Step 1: Update `_build_memory_backend` in `sage/agent.py`**

The change is on lines 87-96. Replace the `LiteLLMEmbedding` import and construction:

```python
# BEFORE (lines 87-96 of sage/agent.py):
        if agent_config.memory.backend == "sqlite":
            from sage.memory.embedding import LiteLLMEmbedding

            logger.info(
                "Building memory backend for '%s': backend=%s, embedding=%s, path=%s",
                agent_config.name,
                agent_config.memory.backend,
                agent_config.memory.embedding,
                agent_config.memory.path,
            )
            embedding = LiteLLMEmbedding(agent_config.memory.embedding)
            kwargs.update({"embedding": embedding, "config": agent_config.memory})

# AFTER:
        if agent_config.memory.backend == "sqlite":
            from sage.memory.embedding import create_embedding

            logger.info(
                "Building memory backend for '%s': backend=%s, embedding=%s, path=%s",
                agent_config.name,
                agent_config.memory.backend,
                agent_config.memory.embedding,
                agent_config.memory.path,
            )
            embedding = create_embedding(agent_config.memory.embedding)
            kwargs.update({"embedding": embedding, "config": agent_config.memory})
```

**Step 2: Update `sage/memory/__init__.py` exports**

Add `OllamaEmbedding` and `create_embedding` to both the import and `__all__`:

```python
# BEFORE:
from sage.memory.embedding import (
    EmbeddingProtocol,
    LiteLLMEmbedding,
    ProviderEmbedding,
)

__all__ = [
    "EmbeddingProtocol",
    "LiteLLMEmbedding",
    "MemoryEntry",
    "MemoryProtocol",
    "ProviderEmbedding",
    "SQLiteMemory",
    "compact_messages",
]

# AFTER:
from sage.memory.embedding import (
    EmbeddingProtocol,
    LiteLLMEmbedding,
    OllamaEmbedding,
    ProviderEmbedding,
    create_embedding,
)

__all__ = [
    "EmbeddingProtocol",
    "LiteLLMEmbedding",
    "MemoryEntry",
    "MemoryProtocol",
    "OllamaEmbedding",
    "ProviderEmbedding",
    "SQLiteMemory",
    "compact_messages",
    "create_embedding",
]
```

**Step 3: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS, no regressions.

**Step 4: Commit**

```bash
git add sage/agent.py sage/memory/__init__.py
git commit -m "feat(memory): wire create_embedding() in agent bootstrap, export new symbols"
```

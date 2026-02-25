# ADR-004: SQLite as Default Memory Backend

## Status
Superseded (embedding approach updated)

## Context
Agents need persistent memory with semantic recall capability. The default memory backend must work out of the box without external services (no Redis, no Pinecone, no API keys). It should support storing text, retrieving by semantic similarity, and compacting old conversations.

## Decision
Use SQLite (via `aiosqlite`) as the storage backend with litellm-based embeddings for embedding generation. Embeddings are stored as numpy float32 blobs alongside the text content. Recall performs cosine similarity search across all stored embeddings.

The memory system is behind a `MemoryProtocol` interface, allowing alternative backends to be swapped in.

## Consequences
**Positive:**
- Zero-config: works with any litellm-supported embedding model (no local model downloads)
- Single-file database, easy to inspect, back up, and reset
- Semantic search via cosine similarity on dense embeddings
- `MemoryProtocol` enables future backends (PostgreSQL/pgvector, ChromaDB, etc.)
- Default model (`text-embedding-3-large`) is fast and inexpensive via API

**Negative:**
- Requires an API key for the embedding provider (not fully offline)
- SQLite cosine similarity is a linear scan (not indexed), which degrades at scale
- Not suitable for production workloads with millions of memories

## Update History
- **Original decision**: Used `sentence-transformers` (`all-MiniLM-L6-v2`) for local embedding generation. This was replaced with litellm-based embeddings to eliminate the ~500MB torch/transformers install footprint and align with the SDK's existing litellm integration. The `MemoryConfig.embedding` field now accepts any litellm model string (default: `text-embedding-3-large`).

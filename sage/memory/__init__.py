"""Memory system for Sage."""

from sage.memory.base import MemoryEntry, MemoryProtocol
from sage.memory.compaction import compact_messages
from sage.memory.embedding import (
    EmbeddingProtocol,
    LiteLLMEmbedding,
    OllamaEmbedding,
    ProviderEmbedding,
    create_embedding,
)
from sage.memory.sqlite_backend import SQLiteMemory

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

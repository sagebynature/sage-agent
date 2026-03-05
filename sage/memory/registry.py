from __future__ import annotations

from typing import Callable

from sage.memory.base import MemoryProtocol
from sage.memory.file_backend import FileMemory
from sage.memory.sqlite_backend import SQLiteMemory

_BACKEND_REGISTRY: dict[str, Callable[..., MemoryProtocol]] = {}


def register_backend(name: str, factory: Callable[..., MemoryProtocol]) -> None:
    _BACKEND_REGISTRY[name] = factory


def get_backend(name: str) -> Callable[..., MemoryProtocol]:
    if name not in _BACKEND_REGISTRY:
        raise ValueError(f"Unknown memory backend: {name!r}. Available: {list(_BACKEND_REGISTRY)}")
    return _BACKEND_REGISTRY[name]


def list_backends() -> list[str]:
    return list(_BACKEND_REGISTRY)


# Register built-in backends at module load
register_backend("sqlite", lambda **kw: SQLiteMemory(**kw))
register_backend("file", lambda **kw: FileMemory(**kw))

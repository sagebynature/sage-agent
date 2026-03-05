from __future__ import annotations

from collections.abc import Iterator

import pytest

import sage.memory.registry as memory_registry
from sage.memory.file_backend import FileMemory


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    original = dict(memory_registry._BACKEND_REGISTRY)
    yield
    memory_registry._BACKEND_REGISTRY.clear()
    memory_registry._BACKEND_REGISTRY.update(original)


class TestMemoryRegistry:
    def test_builtin_backends_registered(self) -> None:
        backends = memory_registry.list_backends()
        assert "sqlite" in backends
        assert "file" in backends

    def test_get_backend_file_factory(self, tmp_path) -> None:
        factory = memory_registry.get_backend("file")
        backend = factory(path=tmp_path / "memory.json")
        assert isinstance(backend, FileMemory)

    def test_get_backend_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown memory backend"):
            memory_registry.get_backend("missing")

    def test_register_backend_custom_factory(self) -> None:
        def custom_factory(**kw):
            return {"kind": "custom", "kwargs": kw}

        memory_registry.register_backend("custom", custom_factory)
        factory = memory_registry.get_backend("custom")
        assert "custom" in memory_registry.list_backends()
        assert factory(path="memory-path") == {
            "kind": "custom",
            "kwargs": {"path": "memory-path"},
        }

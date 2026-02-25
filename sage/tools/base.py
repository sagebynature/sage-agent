"""Abstract base class for stateful tools with lifecycle management."""

from __future__ import annotations

import abc
from typing import Any, Callable


class ToolBase(abc.ABC):
    """Base class for stateful tools that need setup/teardown.

    Subclasses decorate methods with ``@tool`` and the base class collects
    them on instantiation.  Lifecycle hooks (``setup`` / ``teardown``) are
    available for resource management.

    Example::

        class MyTool(ToolBase):
            @tool
            def greet(self, name: str) -> str:
                \"\"\"Say hello.\"\"\"
                return f"Hello, {name}!"

            async def setup(self) -> None:
                # acquire resources
                ...

            async def teardown(self) -> None:
                # release resources
                ...
    """

    def __init__(self) -> None:
        self._tools: list[Callable[..., Any]] = []
        for attr_name in dir(self):
            if attr_name.startswith("_"):
                continue
            attr = getattr(self, attr_name, None)
            if callable(attr) and hasattr(attr, "__tool_schema__"):
                self._tools.append(attr)

    async def setup(self) -> None:
        """Called before the tool is first used. Override to acquire resources."""

    async def teardown(self) -> None:
        """Called when the tool is no longer needed. Override to release resources."""

    def get_tools(self) -> list[Callable[..., Any]]:
        """Return all bound methods decorated with ``@tool``."""
        return list(self._tools)

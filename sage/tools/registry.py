"""Tool registry for managing and dispatching tool calls."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
from typing import TYPE_CHECKING, Any, Callable

from sage.exceptions import PermissionError as SagePermissionError, ToolError
from sage.models import ToolSchema
from sage.tools.base import ToolBase

if TYPE_CHECKING:
    from sage.mcp.client import MCPClient

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry that stores tool functions and dispatches calls by name.

    Supports registering plain ``@tool``-decorated functions, ``ToolBase``
    subclass instances, and bulk-loading from module paths.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._schemas: dict[str, ToolSchema] = {}
        self._instances: list[ToolBase] = []
        self._mcp_tools: dict[str, MCPClient] = {}
        self._permission_handler: Any | None = None

    def register(self, fn_or_instance: Callable[..., Any] | ToolBase) -> None:
        """Register a ``@tool``-decorated function or a ``ToolBase`` instance."""
        if isinstance(fn_or_instance, ToolBase):
            self._instances.append(fn_or_instance)
            for method in fn_or_instance.get_tools():
                self._register_callable(method)
        elif callable(fn_or_instance) and hasattr(fn_or_instance, "__tool_schema__"):
            self._register_callable(fn_or_instance)
        else:
            raise ToolError(
                f"Cannot register {fn_or_instance!r}: "
                "must be a @tool-decorated function or a ToolBase instance"
            )

    def _register_callable(self, fn: Callable[..., Any]) -> None:
        schema: ToolSchema = fn.__tool_schema__  # type: ignore[attr-defined]
        self._tools[schema.name] = fn
        self._schemas[schema.name] = schema
        logger.debug("Registered tool: %s", schema.name)

    def register_mcp_tool(self, schema: ToolSchema, client: MCPClient) -> None:
        """Register an MCP-backed tool from a discovered schema.

        The schema is stored for advertisement to the LLM.  Calls to
        :meth:`execute` for this tool name will be routed through *client*.
        """
        self._schemas[schema.name] = schema
        self._mcp_tools[schema.name] = client
        logger.debug("Registered MCP tool: %s", schema.name)

    def set_permission_handler(self, handler: Any) -> None:
        """Set a permission handler for pre-dispatch checks."""
        self._permission_handler = handler

    def get_schemas(self) -> list[ToolSchema]:
        """Return schemas for all registered tools."""
        return list(self._schemas.values())

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """Dispatch a tool call by name and return the stringified result.

        If a permission handler is set, the tool call is checked first.
        Raises ``PermissionError`` if denied, ``ToolError`` if tool not found
        or execution fails.
        """
        fn = self._tools.get(name)
        mcp_client = self._mcp_tools.get(name)
        if fn is None and mcp_client is None:
            raise ToolError(f"Unknown tool: {name!r}")

        # Permission check.
        if self._permission_handler is not None:
            from sage.permissions.base import PermissionAction

            decision = await self._permission_handler.check(name, arguments)
            if decision.action == PermissionAction.DENY:
                reason = f"Permission denied: {name!r}"
                if decision.reason:
                    reason += f". {decision.reason}"
                raise SagePermissionError(reason)

            if decision.action == PermissionAction.ASK:
                logger.warning(
                    "Permission ASK for tool %r but no interactive handler registered; allowing.",
                    name,
                )

        logger.debug("Executing tool: %s, args=%s", name, list(arguments.keys()))
        try:
            if mcp_client is not None:
                return await mcp_client.call_tool(name, arguments)
            assert fn is not None
            if inspect.iscoroutinefunction(fn):
                result = await fn(**arguments)
            else:
                result = await asyncio.to_thread(fn, **arguments)
        except (ToolError, SagePermissionError):
            raise
        except Exception as exc:
            raise ToolError(f"Tool {name!r} failed: {exc}") from exc

        return str(result)

    _BUILTIN_PREFIX = "builtin"
    _BUILTIN_MODULE = "sage.tools.builtins"

    # Names of all tools shipped in the built-in module.  A bare entry in a
    # config that matches one of these names is auto-resolved to the builtins
    # module without requiring any prefix.
    _BUILTIN_TOOL_NAMES: frozenset[str] = frozenset(
        [
            "shell",
            "file_read",
            "file_write",
            "http_request",
            "memory_store",
            "memory_recall",
        ]
    )

    # Tools in separate modules that can be loaded by bare name.
    _TOOL_MODULE_MAP: dict[str, str] = {
        "file_edit": "sage.tools.file_tools",
        "glob_find": "sage.tools.file_tools",
        "grep_search": "sage.tools.file_tools",
        "git_status": "sage.tools.git_tools",
        "git_diff": "sage.tools.git_tools",
        "git_commit": "sage.tools.git_tools",
        "git_log": "sage.tools.git_tools",
        "git_checkout": "sage.tools.git_tools",
        "git_pr_create": "sage.tools.git_tools",
        "web_search": "sage.tools.web_tools",
        "web_fetch": "sage.tools.web_tools",
    }

    def load_from_module(self, module_path: str) -> None:
        """Import a module and register all ``@tool``-decorated callables.

        *module_path* can be any of:

        - A bare built-in tool name (e.g. ``"shell"``, ``"file_read"``) —
          resolved automatically to the built-in module.
        - ``"builtin"`` — registers **all** built-in tools.
        - ``"builtin:<name>"`` — registers a single built-in tool by name.
        - A dotted module path (``"myapp.tools"``) — registers every
          ``@tool``-decorated function and every ``ToolBase`` subclass found
          at module level.
        - A colon-separated path (``"myapp.tools:search"``) — registers only
          the named attribute.
        """
        # Auto-resolve bare built-in tool names (no dots, no colons).
        if module_path in self._BUILTIN_TOOL_NAMES:
            module_path = f"{self._BUILTIN_MODULE}:{module_path}"
        # Auto-resolve new tool module names.
        elif module_path in self._TOOL_MODULE_MAP:
            module_path = f"{self._TOOL_MODULE_MAP[module_path]}:{module_path}"
        # Expand legacy "builtin" / "builtin:<name>" shorthands.
        elif module_path == self._BUILTIN_PREFIX:
            module_path = self._BUILTIN_MODULE
        elif module_path.startswith(f"{self._BUILTIN_PREFIX}:"):
            _, tool_name = module_path.split(":", 1)
            module_path = f"{self._BUILTIN_MODULE}:{tool_name}"

        if ":" in module_path:
            mod_name, attr_name = module_path.rsplit(":", 1)
            mod = importlib.import_module(mod_name)
            attr = getattr(mod, attr_name, None)
            if attr is None:
                raise ToolError(f"Attribute {attr_name!r} not found in module {mod_name!r}")
            self.register(attr)
        else:
            mod = importlib.import_module(module_path)
            for name in dir(mod):
                if name.startswith("_"):
                    continue
                attr = getattr(mod, name)
                if isinstance(attr, ToolBase):
                    self.register(attr)
                elif callable(attr) and hasattr(attr, "__tool_schema__"):
                    self.register(attr)

"""Tool registry for managing and dispatching tool calls."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
from dataclasses import dataclass
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any, Callable, Literal

from sage.exceptions import PermissionError as SagePermissionError, ToolError
from sage.models import ToolMetadata, ToolResult, ToolSchema
from sage.tools.base import ToolBase
from sage.tracing import span

if TYPE_CHECKING:
    from sage.config import Permission
    from sage.mcp.client import MCPClient

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _MCPToolBinding:
    """Registry entry for a namespaced MCP tool."""

    client: MCPClient
    upstream_name: str
    server_name: str


CATEGORY_TOOLS: dict[str, list[str]] = {
    "read": ["file_read"],
    "edit": ["file_write", "file_edit"],
    "shell": ["shell"],
    "web": ["web_fetch", "web_search", "http_request"],
    "memory": ["memory_store", "memory_recall"],
    "process": [
        "process_start",
        "process_send",
        "process_read",
        "process_wait",
        "process_kill",
        "process_list",
    ],
    "task": [],
    "git": [
        "git_status",
        "git_diff",
        "git_log",
        "git_commit",
        "git_branch",
        "git_undo",
        "git_worktree_create",
        "git_worktree_remove",
        "snapshot_create",
        "snapshot_restore",
        "snapshot_list",
    ],
}

CATEGORY_ARG_MAP: dict[str, str | None] = {
    "read": "path",
    "edit": "path",
    "shell": "command",
    "web": "url",
    "memory": None,
    "process": "command",
    "task": None,
    "git": None,
}

# Modules containing ToolBase instances for each category.
# Used by register_from_permissions to load entire modules when a category is enabled.
_CATEGORY_MODULES: dict[str, list[str]] = {
    "git": ["sage.git.tools", "sage.git.snapshot"],
}


class ToolRegistry:
    """Central registry that stores tool functions and dispatches calls by name.

    Supports registering plain ``@tool``-decorated functions, ``ToolBase``
    subclass instances, and bulk-loading from module paths.
    """

    def __init__(self, default_timeout: float | None = None) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._schemas: dict[str, ToolSchema] = {}
        self._instances: list[ToolBase] = []
        self._mcp_tools: dict[str, _MCPToolBinding] = {}
        self._permission_handler: Any | None = None
        self._default_timeout: float | None = default_timeout
        self._ask_policy: Literal["allow", "deny", "error"] = "error"
        self._allowed_tools: set[str] | None = None
        self._blocked_tools: set[str] = set()
        self._event_emitter: (
            Callable[[str, dict[str, Any]], Awaitable[dict[str, Any] | None]] | None
        ) = None

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

    def register_mcp_tool(self, server_name: str, schema: ToolSchema, client: MCPClient) -> None:
        """Register an MCP-backed tool from a discovered schema.

        The schema is stored for advertisement to the LLM.  Calls to
        :meth:`execute` for this tool name will be routed through *client*.
        """
        runtime_name = f"mcp_{server_name}_{schema.name}"
        metadata = schema.metadata or ToolMetadata()
        runtime_schema = schema.model_copy(
            update={
                "name": runtime_name,
                "metadata": metadata.model_copy(
                    update={
                        "resource_kind": "mcp",
                        "visible_name": schema.name,
                    }
                ),
            }
        )
        self._schemas[runtime_name] = runtime_schema
        self._mcp_tools[runtime_name] = _MCPToolBinding(
            client=client,
            upstream_name=schema.name,
            server_name=server_name,
        )
        logger.debug("Registered MCP tool: %s -> %s", runtime_name, schema.name)

    def set_permission_handler(self, handler: Any) -> None:
        """Set a permission handler for pre-dispatch checks."""
        self._permission_handler = handler

    def set_event_emitter(
        self,
        emitter: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any] | None]],
    ) -> None:
        """Register a callback for tool-adjacent lifecycle events."""
        self._event_emitter = emitter

    def set_ask_policy(self, policy: Literal["allow", "deny", "error"]) -> None:
        """Set how ASK-gated tool calls are handled in headless/CI mode.

        Args:
            policy: One of:
                - ``"allow"``  — proceed as if the user approved.
                - ``"deny"``   — raise :class:`SagePermissionError` immediately.
                - ``"error"``  — raise with a verbose message asking the caller
                              to wire an interactive permission handler (default).
        """
        self._ask_policy = policy

    def set_restrictions(
        self, allowed: list[str] | None = None, blocked: list[str] | None = None
    ) -> None:
        """Set tool allowlist/blocklist restrictions for this registry.

        When *allowed* is set, only tools in the allowlist are visible/executable.
        When *blocked* is set, those tools are hidden/blocked regardless.
        Blocklist takes precedence over allowlist.
        """
        self._allowed_tools = set(allowed) if allowed is not None else None
        self._blocked_tools = set(blocked) if blocked is not None else set()

    def get_schemas(self) -> list[ToolSchema]:
        """Return schemas for all registered tools, applying restrictions."""
        schemas = list(self._schemas.values())
        if self._allowed_tools is not None:
            schemas = [s for s in schemas if s.name in self._allowed_tools]
        if self._blocked_tools:
            schemas = [s for s in schemas if s.name not in self._blocked_tools]
        return schemas

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """Dispatch a tool call and return a backward-compatible text result."""
        result = await self.execute_result(name, arguments)
        return result.render_text()

    def _normalize_tool_result(self, result: Any) -> ToolResult:
        """Normalize raw tool output into a structured ToolResult."""
        if isinstance(result, ToolResult):
            return result
        if isinstance(result, str):
            return ToolResult(text=result)
        return ToolResult(text=str(result))

    async def execute_result(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Dispatch a tool call by name and return a structured result.

        If a permission handler is set, the tool call is checked first.
        Raises ``PermissionError`` if denied, ``ToolError`` if tool not found
        or execution fails.
        """
        fn = self._tools.get(name)
        mcp_binding = self._mcp_tools.get(name)
        if fn is None and mcp_binding is None:
            raise ToolError(f"Unknown tool: {name!r}")

        # Tool restriction check (allowlist/blocklist).
        if self._allowed_tools is not None and name not in self._allowed_tools:
            raise SagePermissionError(
                f"Tool {name!r} is not in the allowed tools list for this agent."
            )
        if name in self._blocked_tools:
            raise SagePermissionError(f"Tool {name!r} is explicitly blocked for this agent.")

        # Permission check.
        if self._permission_handler is not None:
            from sage.permissions.base import PermissionAction

            if self._event_emitter is not None:
                await self._event_emitter(
                    "pre_permission_check",
                    {
                        "tool_name": name,
                        "arguments": arguments,
                    },
                )
            decision = await self._permission_handler.check(name, arguments)
            if self._event_emitter is not None:
                await self._event_emitter(
                    "post_permission_check",
                    {
                        "tool_name": name,
                        "arguments": arguments,
                        "action": decision.action.value,
                        "reason": decision.reason,
                    },
                )
            if decision.action == PermissionAction.DENY:
                reason = f"Permission denied: {name!r}"
                if decision.reason:
                    reason += f". {decision.reason}"
                raise SagePermissionError(reason)

            if decision.action == PermissionAction.ASK:
                if self._ask_policy == "allow":
                    # Proceed as if the user approved — fall through to execute.
                    pass
                elif self._ask_policy == "deny":
                    raise SagePermissionError(f"Permission denied (ASK auto-denied): {name!r}")
                else:
                    # Default "error" behaviour — fail with verbose guidance.
                    reason = (
                        f"Permission ASK for tool {name!r} but no interactive handler "
                        "is registered. Wire an interactive permission handler or change "
                        "the policy to 'allow'/'deny' explicitly."
                    )
                    logger.error(reason)
                    raise SagePermissionError(reason)

        logger.debug("Executing tool: %s, args=%s", name, list(arguments.keys()))
        async with span("tool.execute", {"tool.name": name}) as tool_span:
            tool_span.set_attribute("tool.args", str(list(arguments.keys())))
            try:
                if mcp_binding is not None:
                    return self._normalize_tool_result(
                        await mcp_binding.client.call_tool(mcp_binding.upstream_name, arguments)
                    )
                assert fn is not None
                if inspect.iscoroutinefunction(fn):
                    coro = fn(**arguments)
                else:
                    coro = asyncio.to_thread(fn, **arguments)

                # Per-tool timeout takes precedence over registry default.
                per_tool = getattr(fn, "__tool_timeout__", None)
                effective_timeout = per_tool if per_tool is not None else self._default_timeout

                if effective_timeout is not None:
                    try:
                        result = await asyncio.wait_for(coro, timeout=effective_timeout)
                    except asyncio.TimeoutError:
                        raise ToolError(f"Tool {name!r} timed out after {effective_timeout}s")
                else:
                    result = await coro
            except (ToolError, SagePermissionError):
                raise
            except Exception as exc:
                raise ToolError(f"Tool {name!r} failed: {exc}") from exc

        return self._normalize_tool_result(result)

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
        "web_search": "sage.tools.web_tools",
        "web_fetch": "sage.tools.web_tools",
        "process_start": "sage.tools.process_tools",
        "process_send": "sage.tools.process_tools",
        "process_read": "sage.tools.process_tools",
        "process_wait": "sage.tools.process_tools",
        "process_kill": "sage.tools.process_tools",
        "process_list": "sage.tools.process_tools",
    }

    def register_from_permissions(
        self,
        permission: Permission,
        default: str = "ask",
        extensions: list[str] | None = None,
    ) -> None:
        from sage.config import Permission

        if not isinstance(permission, Permission):
            raise ToolError(f"Expected Permission, got {type(permission).__name__}")

        for category, tool_names in CATEGORY_TOOLS.items():
            value = getattr(permission, category, None)
            effective = default if value is None else value
            if effective == "deny":
                continue
            for tool_name in tool_names:
                try:
                    self.load_from_module(tool_name)
                except (ToolError, ImportError, ModuleNotFoundError):
                    pass  # tool not yet available

            # Load category modules (for ToolBase classes).
            if category in _CATEGORY_MODULES:
                for mod_path in _CATEGORY_MODULES[category]:
                    try:
                        self.load_from_module(mod_path)
                    except (ToolError, ImportError, ModuleNotFoundError):
                        pass

        for module_path in extensions or []:
            self.load_from_module(module_path)

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
                elif inspect.isclass(attr) and issubclass(attr, ToolBase) and attr is not ToolBase:
                    # Instantiate ToolBase subclasses found at module level
                    # so their @tool-decorated methods are available.
                    try:
                        self.register(attr())
                    except Exception:
                        pass
                elif callable(attr) and hasattr(attr, "__tool_schema__"):
                    self.register(attr)

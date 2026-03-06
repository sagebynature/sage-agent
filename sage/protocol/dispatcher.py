from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable
from uuid import uuid4


Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class MethodDispatcher:
    _SAFE_CONFIG_KEYS = {
        "model",
        "temperature",
        "max_turns",
        "max_depth",
        "parallel_tool_execution",
    }

    def __init__(self, agent: Any, session_manager: Any, server: Any) -> None:
        self.agent = agent
        self.session_manager = session_manager
        self.server = server
        self._handlers: dict[str, Handler] = {}
        self._run_tasks: dict[str, asyncio.Task[Any]] = {}
        self._current_run_id: str | None = None
        self.pending_permissions: dict[str, asyncio.Future[Any]] = {}

        self.register("agent/run", self._handle_agent_run)
        self.register("agent/cancel", self._handle_agent_cancel)
        self.register("session/list", self._handle_session_list)
        self.register("session/resume", self._handle_session_resume)
        self.register("session/clear", self._handle_session_clear)
        self.register("config/get", self._handle_config_get)
        self.register("config/set", self._handle_config_set)
        self.register("tools/list", self._handle_tools_list)
        self.register("permission/respond", self._handle_permission_respond)

    def register(self, method_name: str, handler: Handler) -> None:
        self._handlers[method_name] = handler

    async def dispatch(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        request_id = request.get("id")

        handler = self._handlers.get(method)
        if handler is None:
            return self.server._error_response(request_id, -32601, "Method not found")

        try:
            result = await handler(request)
            return self.server._success_response(request_id, result)
        except (ValueError, TypeError) as exc:
            return self.server._error_response(request_id, -32602, str(exc) or "Invalid params")
        except Exception as exc:
            return self.server._error_response(request_id, -32603, str(exc) or "Internal error")

    def create_permission_future(self, request_id: str) -> asyncio.Future[Any]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self.pending_permissions[request_id] = future
        return future

    async def _handle_agent_run(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.agent is None:
            raise RuntimeError("Agent is not configured")

        params = self._ensure_params_dict(request)
        message = params.get("message")
        if not isinstance(message, str) or not message:
            raise ValueError("'message' must be a non-empty string")

        run_id = str(uuid4())
        task = asyncio.create_task(self.agent.run(message))
        self._run_tasks[run_id] = task
        self._current_run_id = run_id

        def _cleanup(_done: asyncio.Task[Any], rid: str = run_id) -> None:
            self._run_tasks.pop(rid, None)
            if self._current_run_id == rid:
                self._current_run_id = None

        task.add_done_callback(_cleanup)
        return {"status": "started", "runId": run_id}

    async def _handle_agent_cancel(self, request: dict[str, Any]) -> dict[str, Any]:
        params = self._ensure_params_dict(request)
        run_id = params.get("runId")
        if run_id is not None and not isinstance(run_id, str):
            raise ValueError("'runId' must be a string")

        cancel_fn = None if self.agent is None else getattr(self.agent, "cancel", None)
        if callable(cancel_fn):
            cancel_result = cancel_fn()
            if asyncio.iscoroutine(cancel_result):
                await cancel_result

        target_id = run_id or self._current_run_id
        task = self._run_tasks.get(target_id) if target_id is not None else None
        cancelled = False
        if task is not None and not task.done():
            task.cancel()
            cancelled = True

        return {"status": "cancelled", "cancelled": cancelled, "runId": target_id}

    async def _handle_session_list(self, request: dict[str, Any]) -> dict[str, Any]:
        _ = request
        sessions = self.session_manager.list_sessions()
        return {"sessions": [self._serialize(session) for session in sessions]}

    async def _handle_session_resume(self, request: dict[str, Any]) -> dict[str, Any]:
        params = self._ensure_params_dict(request)
        session_id = params.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("'session_id' must be a non-empty string")

        getter = getattr(self.session_manager, "get_session", None)
        if getter is None:
            getter = getattr(self.session_manager, "get", None)
        if getter is None:
            raise RuntimeError("Session manager does not support session retrieval")

        session = getter(session_id)
        return {"session": self._serialize(session)}

    async def _handle_session_clear(self, request: dict[str, Any]) -> dict[str, Any]:
        params = self._ensure_params_dict(request)
        session_id = params.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("'session_id' must be a non-empty string")

        destroyer = getattr(self.session_manager, "destroy_session", None)
        if destroyer is None:
            destroyer = getattr(self.session_manager, "destroy", None)
        if destroyer is None:
            raise RuntimeError("Session manager does not support session deletion")

        cleared = bool(destroyer(session_id))
        return {"cleared": cleared}

    async def _handle_config_get(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.agent is None:
            raise RuntimeError("Agent is not configured")

        params = self._ensure_params_dict(request)
        key = params.get("key")
        if not isinstance(key, str) or not key:
            raise ValueError("'key' must be a non-empty string")

        value = getattr(self.agent, key, None)
        return {"key": key, "value": self._serialize(value)}

    async def _handle_config_set(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.agent is None:
            raise RuntimeError("Agent is not configured")

        params = self._ensure_params_dict(request)
        key = params.get("key")
        if not isinstance(key, str) or not key:
            raise ValueError("'key' must be a non-empty string")
        if key not in self._SAFE_CONFIG_KEYS:
            raise ValueError(f"Unsupported runtime config key: {key}")

        value = params.get("value")
        setattr(self.agent, key, value)
        return {"key": key, "value": self._serialize(value)}

    async def _handle_tools_list(self, request: dict[str, Any]) -> dict[str, Any]:
        _ = request
        if self.agent is None:
            return {"tools": []}

        registry = getattr(self.agent, "tool_registry", None)
        if registry is None:
            return {"tools": []}

        schemas = registry.get_schemas()
        return {"tools": [self._serialize(schema) for schema in schemas]}

    async def _handle_permission_respond(self, request: dict[str, Any]) -> dict[str, Any]:
        params = self._ensure_params_dict(request)
        request_id = params.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("'request_id' must be a non-empty string")

        future = self.pending_permissions.pop(request_id, None)
        if future is None:
            return {"resolved": False}

        if not future.done():
            future.set_result(params)
        return {"resolved": True}

    @staticmethod
    def _ensure_params_dict(request: dict[str, Any]) -> dict[str, Any]:
        params = request.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("'params' must be an object")
        return params

    @staticmethod
    def _serialize(value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, list):
            return [MethodDispatcher._serialize(item) for item in value]
        if isinstance(value, dict):
            return {k: MethodDispatcher._serialize(v) for k, v in value.items()}
        return value

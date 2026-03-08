from __future__ import annotations

import itertools
import logging
from contextvars import ContextVar
from typing import Any
from typing import TYPE_CHECKING

from sage.events import (
    BackgroundTaskCompleted,
    DelegationCompleted,
    DelegationStarted,
    LLMStreamDelta,
    LLMTurnCompleted,
    LLMTurnStarted,
    ToolCompleted,
    ToolStarted,
)
from sage.telemetry import EventEnvelope

if TYPE_CHECKING:
    from sage.agent import Agent
    from sage.protocol.server import JsonRpcServer

logger = logging.getLogger(__name__)
_agent_path_var: ContextVar[list[str]] = ContextVar("agent_path", default=[])


def _to_camel_case(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _camelize(value: Any) -> Any:
    if isinstance(value, dict):
        return {_to_camel_case(str(key)): _camelize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_camelize(item) for item in value]
    return value


class JsonRpcEventSink:
    """Publishes canonical telemetry envelopes to JSON-RPC clients."""

    def __init__(self, server: "JsonRpcServer") -> None:
        self._server = server

    async def write(self, envelope: EventEnvelope) -> None:
        payload = _camelize(envelope.model_dump(mode="json"))
        await self._server.send_notification("event/emitted", payload)


class EventBridge:
    """Translates sage-agent events to JSON-RPC notifications."""

    def __init__(self, server: "JsonRpcServer", agent: "Agent") -> None:
        self._server = server
        self._agent = agent
        self._call_counter = itertools.count(1)

    def setup(self) -> None:
        """Register event handlers on the agent."""
        root_agent = getattr(self._agent, "name", "")
        _agent_path_var.set([root_agent])
        self._pending_calls: dict[str, list[str]] = {}
        telemetry_recorder = getattr(self._agent, "_telemetry_recorder", None)
        if telemetry_recorder is not None and hasattr(telemetry_recorder, "_sinks"):
            sinks = telemetry_recorder._sinks
            if not any(isinstance(sink, JsonRpcEventSink) for sink in sinks):
                sinks.append(JsonRpcEventSink(self._server))
        self._agent.on(LLMStreamDelta, self._on_stream_delta)
        self._agent.on(ToolStarted, self._on_tool_started)
        self._agent.on(ToolCompleted, self._on_tool_completed)
        self._agent.on(LLMTurnStarted, self._on_turn_started)
        self._agent.on(LLMTurnCompleted, self._on_turn_completed)
        self._agent.on(DelegationStarted, self._on_delegation_started)
        self._agent.on(DelegationCompleted, self._on_delegation_completed)
        self._agent.on(BackgroundTaskCompleted, self._on_background_completed)

    async def _on_stream_delta(self, event: LLMStreamDelta) -> None:
        try:
            await self._server.send_notification(
                "stream/delta",
                self._with_optional(
                    {
                        "delta": event.delta,
                        "turn": event.turn,
                        "agent_path": event.agent_path or self._get_agent_path(),
                        "runId": event.run_id,
                        "sessionId": event.session_id,
                        "originatingSessionId": event.originating_session_id,
                    }
                ),
            )
        except Exception as e:
            logger.error(f"Bridge error: {e}")

    async def _on_tool_started(self, event: ToolStarted) -> None:
        try:
            call_id = event.call_id or f"call_{next(self._call_counter)}_{event.name}"
            self._pending_calls.setdefault(event.name, []).append(call_id)
            await self._server.send_notification(
                "tool/started",
                self._with_optional(
                    {
                        "toolName": event.name,
                        "callId": call_id,
                        "arguments": event.arguments,
                        "agent_path": event.agent_path or self._get_agent_path(),
                        "runId": event.run_id,
                        "sessionId": event.session_id,
                        "originatingSessionId": event.originating_session_id,
                    }
                ),
            )
        except Exception as e:
            logger.error(f"Bridge error: {e}")

    async def _on_tool_completed(self, event: ToolCompleted) -> None:
        try:
            pending = self._pending_calls.get(event.name, [])
            await self._server.send_notification(
                "tool/completed",
                self._with_optional(
                    {
                        "toolName": event.name,
                        "callId": event.call_id
                        or (pending.pop(0) if pending else f"call_0_{event.name}"),
                        "result": event.result,
                        "durationMs": event.duration_ms,
                        "error": event.error,
                        "agent_path": event.agent_path or self._get_agent_path(),
                        "runId": event.run_id,
                        "sessionId": event.session_id,
                        "originatingSessionId": event.originating_session_id,
                    }
                ),
            )
        except Exception as e:
            logger.error(f"Bridge error: {e}")

    async def _on_turn_started(self, event: LLMTurnStarted) -> None:
        try:
            await self._server.send_notification(
                "turn/started",
                self._with_optional(
                    {
                        "turn": event.turn,
                        "model": event.model,
                        "agent_path": event.agent_path or self._get_agent_path(),
                        "runId": event.run_id,
                        "sessionId": event.session_id,
                        "originatingSessionId": event.originating_session_id,
                    }
                ),
            )
        except Exception as e:
            logger.error(f"Bridge error: {e}")

    async def _on_turn_completed(self, event: LLMTurnCompleted) -> None:
        try:
            usage_payload: dict[str, int | float] = {}
            if event.usage:
                usage_payload = {
                    "input": event.usage.prompt_tokens,
                    "output": event.usage.completion_tokens,
                    "cost": event.usage.cost,
                }

            await self._server.send_notification(
                "turn/completed",
                self._with_optional(
                    {
                        "turn": event.turn,
                        "usage": usage_payload,
                        "agent_path": event.agent_path or self._get_agent_path(),
                        "runId": event.run_id,
                        "sessionId": event.session_id,
                        "originatingSessionId": event.originating_session_id,
                    }
                ),
            )

            await self._send_usage_update()
        except Exception as e:
            logger.error(f"Bridge error: {e}")

    async def _on_delegation_started(self, event: DelegationStarted) -> None:
        try:
            self._push_agent(event.target)
            await self._server.send_notification(
                "delegation/started",
                self._with_optional(
                    {
                        "agentName": event.target,
                        "task": event.task,
                        "depth": len((event.agent_path or self._get_agent_path())) - 1,
                        "agent_path": event.agent_path or self._get_agent_path(),
                        "runId": event.run_id,
                        "sessionId": event.session_id,
                        "originatingSessionId": event.originating_session_id,
                        "delegationId": event.delegation_id,
                    }
                ),
            )
        except Exception as e:
            logger.error(f"Bridge error: {e}")

    async def _on_delegation_completed(self, event: DelegationCompleted) -> None:
        try:
            self._pop_agent()
            result = event.result[:1000]
            await self._server.send_notification(
                "delegation/completed",
                self._with_optional(
                    {
                        "agentName": event.target,
                        "result": result,
                        "duration": event.duration_ms,
                        "agent_path": event.agent_path or self._get_agent_path(),
                        "runId": event.run_id,
                        "sessionId": event.session_id,
                        "originatingSessionId": event.originating_session_id,
                        "delegationId": event.delegation_id,
                    }
                ),
            )
        except Exception as e:
            logger.error(f"Bridge error: {e}")

    async def _on_background_completed(self, event: BackgroundTaskCompleted) -> None:
        try:
            await self._server.send_notification(
                "background/completed",
                self._with_optional(
                    {
                        "taskId": event.task_id,
                        "agentName": event.agent_name,
                        "status": event.status,
                        "result": event.result,
                        "error": event.error,
                        "agent_path": event.agent_path or ["background", event.task_id],
                        "runId": event.run_id,
                        "sessionId": event.session_id,
                        "originatingSessionId": event.originating_session_id,
                    }
                ),
            )
        except Exception as e:
            logger.error(f"Bridge error: {e}")

    async def _send_usage_update(self) -> None:
        stats = self._extract_usage_stats()
        await self._server.send_notification(
            "usage/update",
            {
                "promptTokens": stats["prompt_tokens"],
                "completionTokens": stats["completion_tokens"],
                "totalCost": stats["cost"],
                "model": getattr(self._agent, "model", ""),
                "contextUsagePercent": self._get_context_usage_percent(),
                "agent_path": self._get_agent_path(),
            },
        )

    def _get_agent_path(self) -> list[str]:
        """Get current agent path from contextvars."""
        return list(_agent_path_var.get())

    def _push_agent(self, agent_name: str) -> None:
        """Push agent onto path stack."""
        current = _agent_path_var.get()
        _agent_path_var.set([*current, agent_name])

    def _pop_agent(self) -> None:
        """Pop last agent from path stack."""
        current = _agent_path_var.get()
        if len(current) > 1:
            _agent_path_var.set(current[:-1])

    def _get_context_usage_percent(self) -> int:
        """Get context window usage as an integer percentage (0-100)."""
        if hasattr(self._agent, "get_usage_stats"):
            raw_stats = self._agent.get_usage_stats()
            if isinstance(raw_stats, dict):
                pct = raw_stats.get("usage_percentage")
                if isinstance(pct, (int, float)) and pct is not None:
                    return int(round(pct * 100))
        return 0

    def _extract_usage_stats(self) -> dict[str, int | float]:
        if hasattr(self._agent, "cumulative_usage"):
            usage = self._agent.cumulative_usage
            return {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "cost": getattr(usage, "cost", 0.0),
            }

        if hasattr(self._agent, "get_usage_stats"):
            raw_stats = self._agent.get_usage_stats()
            if isinstance(raw_stats, dict):
                prompt_tokens = raw_stats.get("cumulative_prompt_tokens", 0)
                completion_tokens = raw_stats.get("cumulative_completion_tokens", 0)
                cumulative_cost = raw_stats.get("cumulative_cost", 0.0)
                return {
                    "prompt_tokens": int(prompt_tokens)
                    if isinstance(prompt_tokens, int | float)
                    else 0,
                    "completion_tokens": int(completion_tokens)
                    if isinstance(completion_tokens, int | float)
                    else 0,
                    "cost": float(cumulative_cost)
                    if isinstance(cumulative_cost, int | float)
                    else 0.0,
                }

        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost": 0.0,
        }

    @staticmethod
    def _with_optional(payload: dict[str, object | None]) -> dict[str, object]:
        return {k: v for k, v in payload.items() if v is not None or k == "error"}

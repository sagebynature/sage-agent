"""Core agent class that orchestrates LLM calls, tool execution, and memory."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, TypeVar, cast, overload

from sage.config import AgentConfig, load_config
from sage.hooks.base import HookEvent
from sage.hooks.registry import HookRegistry
from sage.main_config import load_main_config, resolve_and_apply_env, resolve_main_config_path
from sage.tracing import setup_tracing, span

if TYPE_CHECKING:
    from sage.coordination.cancellation import CancellationToken
    from sage.main_config import MainConfig
from sage.exceptions import MaxTurnsExceeded, PermissionError as SagePermissionError, ToolError
from sage.models import CompletionResult, Message, ToolCall, Usage
from sage.providers.litellm_provider import LiteLLMProvider
from sage.skills.loader import (
    Skill,
    filter_skills_by_names,
    load_skills_from_directory,
    resolve_skills_dir,
)
from sage.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from sage.memory.compaction import CompactionController
    from sage.memory.base import MemoryProtocol
    from sage.mcp.client import MCPClient
    from sage.orchestrator.pipeline import Pipeline
    from sage.permissions.base import PermissionProtocol
    from sage.providers.base import ProviderProtocol
    from sage.context.token_budget import TokenBudget

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(slots=True)
class _TurnExecutionResult:
    final_text: str | None
    streamed_chunks: list[str] | None
    tool_calls_executed: bool


def _build_mcp_clients(config: "AgentConfig", agent_config: "AgentConfig") -> list["MCPClient"]:
    _ = config
    mcp_clients: list[MCPClient] = []
    if agent_config.mcp_servers:
        from sage.mcp.client import MCPClient

        for mcp_cfg in agent_config.mcp_servers.values():
            mcp_clients.append(
                MCPClient(
                    transport=mcp_cfg.transport,
                    command=mcp_cfg.command,
                    url=mcp_cfg.url,
                    args=mcp_cfg.args,
                    env=mcp_cfg.env,
                )
            )
    return mcp_clients


def _build_memory_backend(
    config: "AgentConfig", agent_config: "AgentConfig"
) -> "MemoryProtocol | None":
    _ = config
    memory: MemoryProtocol | None = None
    if agent_config.memory is not None:
        from sage.memory.registry import get_backend

        factory = get_backend(agent_config.memory.backend)
        kwargs: dict[str, Any] = {"path": agent_config.memory.path}

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
        elif agent_config.memory.backend == "file":
            logger.info(
                "Building file memory backend for '%s': path=%s",
                agent_config.name,
                agent_config.memory.path,
            )

        memory = factory(**kwargs)
    return memory


def _build_permission_handler(agent_config: "AgentConfig") -> "PermissionProtocol | None":
    permission_handler: PermissionProtocol | None = None
    if agent_config.permission is not None:
        from sage.permissions.base import PermissionAction
        from sage.permissions.policy import CategoryPermissionRule, PolicyPermissionHandler
        from sage.tools.registry import CATEGORY_TOOLS

        rules: list[CategoryPermissionRule] = []
        for category in CATEGORY_TOOLS:
            category_permission = getattr(agent_config.permission, category, None)
            if category_permission is None:
                continue
            if isinstance(category_permission, dict):
                rules.append(
                    CategoryPermissionRule(
                        category=category,
                        action=PermissionAction.ASK,
                        patterns={
                            pattern: PermissionAction(action)
                            for pattern, action in category_permission.items()
                        },
                    )
                )
                continue
            rules.append(
                CategoryPermissionRule(
                    category=category,
                    action=PermissionAction(category_permission),
                )
            )

        permission_handler = PolicyPermissionHandler(
            rules=rules,
            default=PermissionAction.ASK,
        )
    return permission_handler


def _build_token_budget(agent_config: "AgentConfig") -> "TokenBudget | None":
    token_budget: TokenBudget | None = None
    if agent_config.context is not None:
        from sage.context.token_budget import TokenBudget

        try:
            token_budget = TokenBudget(
                model=agent_config.model,
                compaction_threshold=agent_config.context.compaction_threshold,
                reserve_tokens=agent_config.context.reserve_tokens,
            )
        except Exception as exc:
            logger.warning("Failed to create TokenBudget: %s", exc)
    return token_budget


def _build_hook_registry(agent_config: "AgentConfig") -> "HookRegistry":
    """Build a HookRegistry from agent config, wiring built-in hooks."""
    registry = HookRegistry()

    if agent_config.credential_scrubbing is not None and agent_config.credential_scrubbing.enabled:
        from sage.hooks.builtin.credential_scrubber import make_credential_scrubber

        registry.register(HookEvent.POST_TOOL_EXECUTE, make_credential_scrubber())

    if agent_config.query_classification is not None and agent_config.query_classification.rules:
        from sage.hooks.builtin.query_classifier import ClassificationRule, make_query_classifier

        rules = [
            ClassificationRule(
                keywords=[r.pattern],
                patterns=[],
                priority=r.priority,
                target_model=r.model,
            )
            for r in agent_config.query_classification.rules
        ]
        registry.register(HookEvent.PRE_LLM_CALL, make_query_classifier(rules))

    if agent_config.follow_through is not None and agent_config.follow_through.enabled:
        from sage.hooks.builtin.follow_through import make_follow_through_hook

        registry.register(HookEvent.POST_LLM_CALL, make_follow_through_hook())

    if (
        agent_config.planning
        and agent_config.planning.analysis
        and agent_config.planning.analysis.enabled
    ):
        from sage.hooks.builtin.plan_analyzer import make_plan_analyzer

        registry.register(
            HookEvent.ON_PLAN_CREATED,
            make_plan_analyzer(prompt=agent_config.planning.analysis.prompt),
            modifying=True,
        )

    if agent_config.planning:
        from sage.hooks.builtin.notepad_injector import make_notepad_hook

        registry.register(
            HookEvent.PRE_LLM_CALL,
            make_notepad_hook("default"),
            modifying=True,
        )

    return registry


def _wire_post_construction(
    agent: Agent,
    config: dict[str, Any],
    agent_config: AgentConfig,
) -> None:
    permission_handler = cast("PermissionProtocol | None", config["permission_handler"])
    token_budget = cast("TokenBudget | None", config["token_budget"])
    base_dir = cast(Path, config["base_dir"])

    if agent_config.allowed_tools is not None or agent_config.blocked_tools is not None:
        agent.tool_registry.set_restrictions(
            allowed=agent_config.allowed_tools,
            blocked=agent_config.blocked_tools,
        )

    if agent_config.permission is not None:
        agent.tool_registry.register_from_permissions(
            agent_config.permission,
            extensions=agent_config.extensions or None,
        )
    elif agent_config.extensions:
        for extension_path in agent_config.extensions:
            agent.tool_registry.load_from_module(extension_path)

    if agent.memory is not None:
        agent._register_memory_tools()

    if (
        agent_config.memory is not None
        and agent_config.memory.auto_load
        and agent.memory is not None
    ):
        from sage.hooks.builtin.auto_memory import make_auto_memory_hook

        agent._hook_registry.register(
            HookEvent.PRE_LLM_CALL,
            make_auto_memory_hook(agent.memory, max_memories=agent_config.memory.auto_load_top_k),
        )

    if permission_handler is not None:
        agent.tool_registry.set_permission_handler(permission_handler)

    shell_allow: frozenset[str] | None = None
    if agent_config.permission is not None and isinstance(agent_config.permission.shell, dict):
        patterns = [
            k for k, v in agent_config.permission.shell.items() if v == "allow" and k != "*"
        ]
        if patterns:
            shell_allow = frozenset(patterns)

    shell_dangerous_patterns = agent_config.shell_dangerous_patterns

    if agent_config.sandbox is not None:
        from sage.tools._sandbox import build_sandbox
        from sage.tools.builtins import make_sandboxed_shell

        sandbox = build_sandbox(agent_config.sandbox)
        sandboxed_shell = make_sandboxed_shell(
            sandbox,
            allowed_commands=shell_allow,
            dangerous_patterns=shell_dangerous_patterns,
        )
        agent.tool_registry.register(sandboxed_shell)
    elif shell_allow is not None or shell_dangerous_patterns is not None:
        from sage.tools.builtins import make_shell

        agent.tool_registry.register(
            make_shell(
                allowed_commands=shell_allow,
                dangerous_patterns=shell_dangerous_patterns,
            )
        )

    agent._token_budget = token_budget
    agent._git_config = agent_config.git
    agent._memory_config = agent_config.memory

    if (
        agent_config.identity is not None
        and agent_config.identity.format == "aieos"
        and agent_config.identity.file
    ):
        try:
            from sage.identity.aieos import format_identity_prompt, load_identity

            identity_path = (
                base_dir / agent_config.identity.file
                if not Path(agent_config.identity.file).is_absolute()
                else Path(agent_config.identity.file)
            )
            identity = load_identity(identity_path)
            agent._identity_prompt = format_identity_prompt(identity)
        except Exception as exc:
            logger.warning(
                "Failed to load AIEOS identity from %s: %s", agent_config.identity.file, exc
            )

    if agent_config.tracing is not None:
        setup_tracing(agent_config.tracing)

    if agent_config.planning is not None:
        agent._register_planning_tools(agent_config)


def _construct_agent(
    cls: type[Agent],
    agent_config: AgentConfig,
    subagents: dict[str, Agent],
    skills: list[Skill],
    mcp_clients: list[MCPClient],
    memory: MemoryProtocol | None,
    hook_registry: HookRegistry,
) -> Agent:
    return cls(
        name=agent_config.name,
        model=agent_config.model,
        description=agent_config.description,
        max_turns=agent_config.max_turns,
        max_depth=agent_config.max_depth,
        subagents=subagents,
        body=agent_config._body,
        model_params=agent_config.model_params.to_kwargs() or None,
        skills=skills or None,
        mcp_clients=mcp_clients or None,
        memory=memory,
        compaction_threshold=agent_config.memory.compaction_threshold
        if agent_config.memory is not None
        else 50,
        parallel_tool_execution=agent_config.parallel_tool_execution,
        tool_timeout=agent_config.tool_timeout,
        hook_registry=hook_registry,
        prompt_metadata=agent_config.prompt_metadata,
    )


class Agent:
    """Core agent class that orchestrates LLM calls, tool execution, and memory.

    The Agent ties together a provider (LLM), tool registry, optional memory,
    optional MCP servers, and optional subagents into a single execution loop.
    It supports both blocking (``run``) and streaming (``stream``) interaction
    modes.

    Example::

        from sage import Agent
        from sage.tools import tool

        @tool
        def add(a: int, b: int) -> int:
            \"\"\"Add two numbers.\"\"\"
            return a + b

        agent = Agent(
            name="calc",
            model="gpt-4o",
            description="Calculator assistant",
            body="You are a calculator assistant.",
            tools=[add],
        )
        result = await agent.run("What is 2 + 3?")
    """

    def __init__(
        self,
        name: str,
        model: str,
        description: str = "",
        tools: list[Any] | None = None,
        memory: MemoryProtocol | None = None,
        subagents: dict[str, Agent] | None = None,
        provider: ProviderProtocol | None = None,
        max_turns: int = 10,
        max_depth: int = 3,
        _current_depth: int = 0,
        body: str = "",
        model_params: dict[str, Any] | None = None,
        skills: list[Skill] | None = None,
        mcp_clients: list[MCPClient] | None = None,
        compaction_threshold: int = 50,
        compaction_controller: CompactionController | None = None,
        parallel_tool_execution: bool = True,
        tool_timeout: float | None = None,
        hook_registry: HookRegistry | None = None,
        prompt_metadata: Any | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.description = description
        self._body = body
        self._prompt_metadata = prompt_metadata
        self.max_turns = max_turns
        self.max_depth = max_depth
        self._current_depth = _current_depth
        self.memory = memory
        self.subagents = subagents or {}
        self.skills: list[Skill] = skills or []
        self._loaded_skills: set[str] = set()
        self.mcp_clients: list[MCPClient] = mcp_clients or []
        self._mcp_initialized = False
        self._memory_initialized = False
        self._conversation_history: list[Message] = []
        self._compaction_threshold: int = compaction_threshold
        self._token_usage: int = 0
        self._cumulative_usage: Usage = Usage()
        self._context_window_limit: int | None = None
        self._token_compaction_threshold: float = 0.8
        self._turns_since_compaction: int = 0
        self._context_window_detected: bool = False
        self._compacted_last_turn: bool = False
        self._token_budget: Any | None = None
        self._git_config: Any | None = None
        self._memory_config: Any | None = None
        self.parallel_tool_execution: bool = parallel_tool_execution
        self._hook_registry: HookRegistry = (
            hook_registry if hook_registry is not None else HookRegistry()
        )
        self._current_turn: int = 0
        self._identity_prompt: str = ""
        self._last_compaction_strategy: str | None = None
        # Session manager for stateful delegations.
        from sage.coordination.session import SessionManager

        self._session_mgr = SessionManager()
        self._main_config: MainConfig | None = None

        # Background task manager for async delegations.
        from sage.coordination.background import BackgroundTaskManager

        self._bg_manager = BackgroundTaskManager()

        # Default to LiteLLM provider if none supplied.
        self.provider: ProviderProtocol = provider or LiteLLMProvider(model, **(model_params or {}))  # type: ignore[assignment]
        self._provider: ProviderProtocol = self.provider

        from sage.memory.compaction import DefaultCompactionController

        self._compaction_controller = compaction_controller or DefaultCompactionController()
        if compaction_controller is None and isinstance(
            self._compaction_controller, DefaultCompactionController
        ):
            self._compaction_controller.threshold = compaction_threshold

        # Build tool registry from the supplied tool list.
        self.tool_registry = ToolRegistry(default_timeout=tool_timeout)
        if tools:
            for t in tools:
                if isinstance(t, str):
                    self.tool_registry.load_from_module(t)
                else:
                    self.tool_registry.register(t)

        # Auto-register delegation tools when subagents are present.
        if self.subagents:
            self._register_delegation_tools()
            self._register_background_tools()

        # Auto-register skill tool when skills are present.
        if self.skills:
            self._register_skill_tool()

    # ── Factory methods ───────────────────────────────────────────────

    @classmethod
    def from_config(cls, path: str | Path, central: MainConfig | None = None) -> Agent:
        """Create an Agent from a Markdown config file or directory containing AGENTS.md."""
        resolved = Path(path)
        if resolved.is_dir():
            resolved = resolved / "AGENTS.md"
        if central is None:
            central = load_main_config(resolve_main_config_path())
        resolve_and_apply_env(central)
        config = load_config(str(resolved), central=central)
        resolved_dir = resolve_skills_dir(central.skills_dir if central else None)
        global_skills = load_skills_from_directory(resolved_dir) if resolved_dir else []
        agent = cls._from_agent_config(config, resolved.parent, global_skills=global_skills)
        agent._main_config = central
        return agent

    @classmethod
    def _from_agent_config(
        cls,
        config: AgentConfig,
        base_dir: Path,
        global_skills: list[Skill] | None = None,
    ) -> Agent:
        """Recursively build an agent (and subagents) from config."""
        global_skills = global_skills or []
        subagents = {
            sub_config.name: cls._from_agent_config(
                sub_config, base_dir, global_skills=global_skills
            )
            for sub_config in config.subagents
        }
        skills = filter_skills_by_names(global_skills, config.skills)
        mcp_clients = _build_mcp_clients(config, config)
        memory = _build_memory_backend(config, config)
        permission_handler = _build_permission_handler(config)
        token_budget = _build_token_budget(config)
        hook_registry = _build_hook_registry(config)
        agent = _construct_agent(cls, config, subagents, skills, mcp_clients, memory, hook_registry)
        _wire_post_construction(
            agent,
            {
                "base_dir": base_dir,
                "permission_handler": permission_handler,
                "token_budget": token_budget,
            },
            config,
        )
        return agent

    # ── Execution methods ─────────────────────────────────────────────

    @overload
    async def run(self, input: str) -> str: ...

    @overload
    async def run(self, input: str, *, response_model: type[T]) -> T: ...

    async def run(self, input: str, *, response_model: type[T] | None = None) -> str | T:
        """Main execution loop: LLM call -> tool execution -> repeat until done.

        Loops for at most ``max_turns`` iterations. Terminates when the model
        produces a response with no tool calls or ``max_turns`` is exceeded.
        Conversation history accumulates across calls.

        MCP servers connect on first call; memory is recalled before the first
        turn and persisted after the final response.

        If ``response_model`` is provided, a JSON schema prompt is injected and
        the final output is parsed into that Pydantic model.
        """
        logger.info("Agent '%s' run started: %s", self.name, input[:80])
        messages = await self._pre_loop_setup(input)
        self._handle_response_model(messages, response_model)

        async with span("agent.run", {"agent.name": self.name, "model": self.model}) as agent_span:
            for turn in range(self.max_turns):
                self._current_turn = turn
                logger.debug("Turn %d/%d", turn + 1, self.max_turns)
                turn_result = await self._execute_turn(messages, turn=turn, streaming=False)
                if turn_result.tool_calls_executed:
                    continue
                logger.info("Agent '%s' run complete after %d turn(s)", self.name, turn + 1)
                final_output = turn_result.final_text or ""
                agent_span.set_attribute("turn_count", turn + 1)
                await self._post_loop_cleanup(input, final_output)
                if response_model is None:
                    return final_output
                return self._parse_response_model_output(response_model, final_output)

            await self._raise_max_turns_exceeded(
                input=input,
                messages=messages,
                agent_span=agent_span,
                during_stream=False,
            )

    async def stream(self, input: str) -> AsyncIterator[str]:
        """Streaming variant of :meth:`run` — yields text chunks as they arrive.

        Like ``run()``, this method loops for up to ``max_turns`` iterations.
        Each iteration streams from the provider, yielding text deltas in
        real-time.  When a streaming turn ends with tool calls, the tools are
        executed (non-streaming) and the results are fed back for the next
        iteration.  The loop terminates when the model produces a response
        with no tool calls or ``max_turns`` is exceeded.

        Conversation history is accumulated across calls so that subsequent
        invocations see the full multi-turn context.
        """
        logger.info("Agent '%s' stream started: %s", self.name, input[:80])
        messages = await self._pre_loop_setup(input)

        async with span(
            "agent.stream", {"agent.name": self.name, "model": self.model}
        ) as agent_span:
            for turn in range(self.max_turns):
                self._current_turn = turn
                logger.debug("Stream turn %d/%d", turn + 1, self.max_turns)
                turn_result = await self._execute_turn(messages, turn=turn, streaming=True)
                for chunk in turn_result.streamed_chunks or []:
                    yield chunk
                if turn_result.tool_calls_executed:
                    continue
                logger.info("Agent '%s' stream complete after %d turn(s)", self.name, turn + 1)
                agent_span.set_attribute("turn_count", turn + 1)
                await self._post_loop_cleanup(input, turn_result.final_text or "")
                return

            await self._raise_max_turns_exceeded(
                input=input,
                messages=messages,
                agent_span=agent_span,
                during_stream=True,
            )

    def _handle_response_model(
        self, messages: list[Message], response_model: type[T] | None
    ) -> None:
        if response_model is None:
            return
        schema = response_model.model_json_schema()  # type: ignore[attr-defined]
        schema_instruction = Message(
            role="system",
            content=f"Respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}",
        )
        insert_idx = next((i for i, m in enumerate(messages) if m.role != "system"), len(messages))
        messages.insert(insert_idx, schema_instruction)

    def _parse_response_model_output(self, response_model: type[T], final_output: str) -> T:
        cleaned = re.sub(r"^```(?:json)?\n?|```$", "", final_output.strip(), flags=re.MULTILINE)
        return response_model.model_validate_json(cleaned.strip())  # type: ignore[attr-defined, no-any-return]

    async def _execute_turn(
        self,
        messages: list[Message],
        *,
        turn: int,
        streaming: bool,
    ) -> _TurnExecutionResult:
        await self._inject_background_notifications(messages)
        tool_schemas = self.tool_registry.get_schemas() or None
        await self._emit(
            HookEvent.PRE_LLM_CALL,
            {
                "model": self.model,
                "messages": messages,
                "tool_schemas": tool_schemas,
                "turn": turn,
            },
        )

        if not streaming:
            result: CompletionResult = await self.provider.complete(messages, tools=tool_schemas)
            self._cumulative_usage += result.usage
            n_tool_calls = len(result.message.tool_calls) if result.message.tool_calls else 0
            await self._emit(
                HookEvent.POST_LLM_CALL,
                {
                    "result": result,
                    "turn": turn,
                    "usage": result.usage,
                    "n_tool_calls": n_tool_calls,
                },
            )
            messages.append(result.message)
            if not result.message.tool_calls:
                return _TurnExecutionResult(
                    final_text=result.message.content or "",
                    streamed_chunks=None,
                    tool_calls_executed=False,
                )
            await self._execute_tool_calls(result.message.tool_calls, messages)
            return _TurnExecutionResult(
                final_text=None,
                streamed_chunks=None,
                tool_calls_executed=True,
            )

        turn_content = ""
        turn_tool_calls: list[ToolCall] | None = None
        turn_usage: Usage | None = None
        streamed_chunks: list[str] = []
        async for chunk in self.provider.stream(messages, tools=tool_schemas):  # type: ignore[attr-defined]
            if chunk.delta:
                turn_content += chunk.delta
                streamed_chunks.append(chunk.delta)
                await self._emit(
                    HookEvent.ON_LLM_STREAM_DELTA, {"delta": chunk.delta, "turn": turn}
                )
            if chunk.tool_calls:
                turn_tool_calls = chunk.tool_calls
            if chunk.usage is not None:
                turn_usage = chunk.usage

        if turn_usage is not None:
            self._cumulative_usage += turn_usage
        assistant_msg = Message(
            role="assistant", content=turn_content or None, tool_calls=turn_tool_calls
        )
        messages.append(assistant_msg)
        n_tool_calls_stream = len(turn_tool_calls) if turn_tool_calls else 0
        await self._emit(
            HookEvent.POST_LLM_CALL,
            {
                "result": assistant_msg,
                "turn": turn,
                "usage": turn_usage,
                "n_tool_calls": n_tool_calls_stream,
            },
        )
        if not turn_tool_calls:
            return _TurnExecutionResult(
                final_text=turn_content,
                streamed_chunks=streamed_chunks,
                tool_calls_executed=False,
            )
        await self._execute_tool_calls(turn_tool_calls, messages)
        return _TurnExecutionResult(
            final_text=None,
            streamed_chunks=streamed_chunks,
            tool_calls_executed=True,
        )

    async def _raise_max_turns_exceeded(
        self,
        input: str,
        messages: list[Message],
        *,
        agent_span: Any,
        during_stream: bool,
    ) -> NoReturn:
        suffix = " during stream" if during_stream else ""
        logger.warning("Agent '%s' reached max_turns (%d)%s", self.name, self.max_turns, suffix)
        agent_span.set_attribute("turn_count", self.max_turns)
        last_content = self._extract_final_output(messages)
        if last_content:
            await self._store_memory(input, last_content)
        raise MaxTurnsExceeded(turns=self.max_turns, last_content=last_content)

    def _detect_context_window_limit(self) -> None:
        if self._context_window_detected:
            return

        self._context_window_detected = True
        self._context_window_limit = None

        # Delegate to the provider so agent.py never imports litellm directly.
        get_context_window = cast(
            Callable[[], int] | None, getattr(self.provider, "get_context_window", None)
        )
        if callable(get_context_window):
            self._context_window_limit = get_context_window()

    def _update_token_usage(self, messages: list[dict[str, Any]]) -> None:
        # Delegate to the provider so agent.py never imports litellm directly.
        count_tokens = cast(
            Callable[[list[dict[str, Any]]], int] | None,
            getattr(self.provider, "count_tokens", None),
        )
        if callable(count_tokens):
            self._token_usage = count_tokens(messages)
        else:
            self._token_usage = 0

    @property
    def cumulative_usage(self) -> Usage:
        """Return the cumulative token usage across all turns in this session."""
        return self._cumulative_usage

    def get_usage_stats(self) -> dict[str, int | float | bool | None]:
        usage_percentage: float | None = None
        if self._context_window_limit and self._context_window_limit > 0:
            usage_percentage = min(1.0, self._token_usage / self._context_window_limit)

        cu = self._cumulative_usage
        return {
            "token_usage": self._token_usage,
            "context_window_limit": self._context_window_limit,
            "usage_percentage": usage_percentage,
            "compacted_this_turn": self._compacted_last_turn,
            "cumulative_prompt_tokens": cu.prompt_tokens,
            "cumulative_completion_tokens": cu.completion_tokens,
            "cumulative_total_tokens": cu.total_tokens,
            "cumulative_cache_read_tokens": cu.cache_read_tokens,
            "cumulative_cache_creation_tokens": cu.cache_creation_tokens,
            "cumulative_reasoning_tokens": cu.reasoning_tokens,
            "cumulative_cost": cu.cost,
        }

    async def delegate(
        self,
        subagent_name: str,
        task: str,
        *,
        session_id: str | None = None,
        category: str | None = None,
    ) -> str:
        """Delegate a task to a named subagent.

        Raises:
            ToolError: If the subagent name is not found.
        """
        if subagent_name not in self.subagents:
            raise ToolError(f"Unknown subagent: {subagent_name}")
        # Enforce max delegation depth.
        if self._current_depth >= self.max_depth:
            raise ToolError(
                f"Max delegation depth ({self.max_depth}) exceeded — "
                f"cannot delegate to '{subagent_name}'"
            )
        logger.debug(
            "Delegating to subagent '%s': %s",
            subagent_name,
            task[:120],
        )
        await self._emit(HookEvent.ON_DELEGATION, {"target": subagent_name, "input": task})
        subagent = self.subagents[subagent_name]
        # Restore conversation history from session if resuming.
        if session_id:
            session = self._session_mgr.get(session_id)
            if session:
                subagent._conversation_history = [m for m in session.messages if m.role != "system"]

        # Apply category-based model routing.
        if category:
            main_config = getattr(self, "_main_config", None)
            if main_config is not None:
                cat_cfg = main_config.categories.get(category)
                if cat_cfg:
                    logger.info(
                        "Category '%s' routing: %s -> model=%s",
                        category,
                        subagent_name,
                        cat_cfg.model,
                    )
                    subagent.model = cat_cfg.model
                    setattr(
                        subagent,
                        "provider",
                        LiteLLMProvider(cat_cfg.model, **cat_cfg.model_params.to_kwargs()),
                    )
        # Propagate depth to subagent.
        subagent._current_depth = self._current_depth + 1

        # Propagate subagent tool/stream events to parent so TUI can display them.
        propagated_events = [
            HookEvent.PRE_TOOL_EXECUTE,
            HookEvent.POST_TOOL_EXECUTE,
            HookEvent.ON_LLM_STREAM_DELTA,
        ]
        forwarding_entries = []
        for evt in propagated_events:
            async def _forward(event: HookEvent, data: dict[str, Any], _e: HookEvent = evt) -> None:
                await self._emit(_e, data)
            from sage.hooks.registry import _HandlerEntry
            entry = _HandlerEntry(handler=_forward, priority=0, modifying=False)
            subagent._hook_registry._handlers[evt].append(entry)
            forwarding_entries.append((evt, entry))

        try:
            result = await subagent.run(task)
        except KeyboardInterrupt:
            raise  # Always propagate user interrupts
        except BaseException as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            logger.error("Subagent '%s' crashed: %s", subagent.name, e, exc_info=True)
            result = f"[Subagent Error] {subagent.name} failed: {type(e).__name__}: {e}"
        finally:
            for evt, entry in forwarding_entries:
                try:
                    subagent._hook_registry._handlers[evt].remove(entry)
                except ValueError:
                    pass

        # Persist subagent conversation history to session.
        effective_sid = session_id or f"{subagent_name}_{int(time.time())}"
        session_state = self._session_mgr.get(effective_sid)
        if session_state is None:
            session_state = self._session_mgr.create(subagent_name, session_id=effective_sid)
        history = getattr(subagent, "_conversation_history", [])
        session_state.messages = list(history)

        await self._emit(
            HookEvent.ON_DELEGATION_COMPLETE, {"target": subagent_name, "result": result}
        )
        # Only surface session ID when caller explicitly provided one.
        if session_id:
            return f"[Session: {effective_sid}]\n{result}"
        return result

    # ── Operator overloads ──────────────────────────────────────────────

    def __rshift__(self, other: Agent | Pipeline) -> Pipeline:
        """Support ``agent >> agent`` pipeline syntax.

        Example::

            pipeline = agent1 >> agent2 >> agent3
            result = await pipeline.run("input")
        """
        from sage.orchestrator.pipeline import Pipeline

        if isinstance(other, Pipeline):
            return Pipeline([self] + other.agents)
        return Pipeline([self, other])

    def on(self, event_class: type[Any], callback: "Callable[[Any], Awaitable[None]]") -> None:
        """Subscribe to a typed agent event.

        Maps *event_class* to its underlying :class:`~sage.hooks.base.HookEvent`
        via :data:`~sage.events.EVENT_TYPE_MAP`, then registers an adapter that
        deserialises the raw hook data dict into a typed instance before calling
        *callback*.

        Args:
            event_class: One of the typed event dataclasses from :mod:`sage.events`
                (e.g. :class:`~sage.events.ToolStarted`).
            callback: An async callable that accepts a single typed event instance.

        Example::

            from sage.events import ToolStarted

            async def handler(e: ToolStarted) -> None:
                print(f"Tool {e.name} started")

            agent.on(ToolStarted, handler)
        """
        from sage.events import EVENT_TYPE_MAP, from_hook_data

        hook_event = EVENT_TYPE_MAP[event_class]

        async def _adapter(event: HookEvent, data: dict[str, Any]) -> None:
            typed = from_hook_data(event_class, data)
            await callback(typed)

        self._hook_registry.register(hook_event, _adapter)

    # ── Private helpers ───────────────────────────────────────────────

    async def _emit(self, event: HookEvent, data: dict[str, Any] | None = None) -> None:
        """Emit a hook event, catching and logging any handler errors."""
        try:
            await self._hook_registry.emit_void(event, data or {})
        except Exception as exc:
            logger.debug("Hook emission error for %s: %s", event, exc)

    async def _pre_loop_setup(self, input: str) -> list[Message]:
        """MCP init, memory init, context window detection, memory recall, build initial messages list."""
        # Connect MCP servers and register their tools on first run.
        await self._ensure_mcp_initialized()
        await self._ensure_memory_initialized()
        if not self._context_window_detected:
            self._detect_context_window_limit()

        # Recall relevant memories and prepend as context.
        memory_context = await self._recall_memory(input)

        messages = self._build_messages(input, memory_context=memory_context)

        await self._maybe_auto_snapshot()

        return messages

    def _is_ask_gated(self, name: str) -> bool:
        """Return True if the tool requires interactive approval (ask policy)."""
        try:
            handler = self.tool_registry._permission_handler
            if handler is None:
                return False
            from sage.permissions.base import PermissionAction
            from sage.permissions.policy import TOOL_TO_CATEGORY

            category = TOOL_TO_CATEGORY.get(name)
            if category is None:
                return False
            matched_action = getattr(handler, "default", PermissionAction.ASK)
            for rule in getattr(handler, "rules", []):
                if getattr(rule, "category", None) == category:
                    matched_action = rule.action
            return matched_action == PermissionAction.ASK
        except Exception:
            return False

    async def _execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
        messages: list[Message],
        token: "CancellationToken | None" = None,
    ) -> None:
        """Execute tool calls and append result messages.

        When parallel_tool_execution is enabled (default), non-ask-gated calls
        run concurrently via asyncio.gather. Ask-gated tools execute sequentially
        so approval prompts are handled one at a time. If *token* is provided and
        cancelled, pending sequential calls are skipped.
        """
        tool_names = [tc.name for tc in tool_calls]
        logger.debug("Dispatching tools: %s", tool_names)

        async def _safe_execute(tc: ToolCall) -> tuple[str, str]:
            if tc.name != "delegate":
                logger.debug(
                    "[%s] Executing tool '%s': %s", self.name, tc.name, str(tc.arguments)[:120]
                )

            try:
                await self._emit(
                    HookEvent.PRE_TOOL_EXECUTE,
                    {
                        "tool_name": tc.name,
                        "arguments": tc.arguments or {},
                        "turn": self._current_turn,
                    },
                )
                _t0 = time.monotonic()
                result = await self.tool_registry.execute(tc.name, tc.arguments or {})
                duration_ms = (time.monotonic() - _t0) * 1000
                result_str = str(result)
                await self._emit(
                    HookEvent.POST_TOOL_EXECUTE,
                    {
                        "tool_name": tc.name,
                        "arguments": tc.arguments or {},
                        "result": result_str,
                        "duration_ms": duration_ms,
                    },
                )
                return tc.id, result_str
            except SagePermissionError:
                raise  # Never swallow permission errors — re-raise so the agent loop can handle them
            except ToolError as exc:
                logger.error("[%s] Tool '%s' failed: %s", self.name, tc.name, exc)
                return tc.id, f"Error executing tool '{tc.name}': {exc}"
            except Exception as exc:
                logger.error("[%s] Tool '%s' raised unexpected error: %s", self.name, tc.name, exc)
                return tc.id, f"Error executing tool '{tc.name}': {exc}"

        # Split into parallel (allow/deny) and sequential (ask-gated) groups.
        parallel_tcs = [tc for tc in tool_calls if not self._is_ask_gated(tc.name)]
        ask_tcs = [tc for tc in tool_calls if self._is_ask_gated(tc.name)]

        pairs: list[tuple[str, str]] = []

        # Execute non-ask-gated tools (parallel or sequential per flag).
        if parallel_tcs:
            if self.parallel_tool_execution:
                raw = await asyncio.gather(
                    *(_safe_execute(tc) for tc in parallel_tcs),
                    return_exceptions=True,
                )
                for item in raw:
                    if isinstance(item, BaseException):
                        raise item
                pairs.extend(cast(list[tuple[str, str]], raw))
            else:
                for tc in parallel_tcs:
                    pairs.append(await _safe_execute(tc))

        # Execute ask-gated tools sequentially, respecting cancellation.
        for tc in ask_tcs:
            if token is not None and token.is_cancelled:
                logger.info("Cancellation token set — skipping remaining ask-gated tools")
                break
            pairs.append(await _safe_execute(tc))

        # Reassemble in original order and append to messages.
        id_to_result = dict(pairs)
        for tc in tool_calls:
            result_text = id_to_result.get(tc.id, f"Tool '{tc.name}' was skipped (cancelled)")
            messages.append(Message(role="tool", content=result_text, tool_call_id=tc.id))

    async def _post_loop_cleanup(self, input: str, final_output: str) -> None:
        """Append to history, compact history, update token usage, store memory."""
        # Persist the user + assistant exchange to conversation history.
        self._conversation_history.append(Message(role="user", content=input))
        self._conversation_history.append(Message(role="assistant", content=final_output))
        await self._maybe_compact_history()
        self._update_token_usage([message.model_dump() for message in self._build_messages("")])
        await self._store_memory(input, final_output)

    def _extract_final_output(self, messages: list[Message]) -> str:
        """Find and return the last assistant text content (used for max-turns fallback)."""
        for msg in reversed(messages):
            if msg.role == "assistant" and msg.content:
                return msg.content
        return ""

    async def _maybe_auto_snapshot(self) -> None:
        """Create a pre-run git snapshot if configured."""
        if self._git_config is None:
            return
        if not self._git_config.auto_snapshot:
            return

        from sage.git.snapshot import GitSnapshot

        snapshot: GitSnapshot | None = None
        for instance in self.tool_registry._instances:
            if isinstance(instance, GitSnapshot):
                snapshot = instance
                break

        if snapshot is None:
            return

        try:
            await snapshot.setup()
            result = await snapshot.snapshot_create(label="pre-run")
            logger.info("Auto-snapshot: %s", result)
        except Exception as exc:
            logger.warning("Auto-snapshot failed: %s", exc)

    def _register_delegation_tools(self) -> None:
        from sage.tools.agent_tools.delegation import register_delegation_tools

        register_delegation_tools(self)

    def _register_memory_tools(self) -> None:
        from sage.tools.agent_tools.memory import register_memory_tools

        register_memory_tools(self)

    def _register_planning_tools(self, config: Any) -> None:
        from sage.tools.agent_tools.planning import register_planning_tools

        register_planning_tools(self, config)

    def _register_background_tools(self) -> None:
        from sage.tools.agent_tools.background import register_background_tools

        register_background_tools(self)

    def _register_skill_tool(self) -> None:
        """Register ``use_skill`` tool when the agent has skills."""
        from sage.tools.agent_tools.skill import register_skill_tool

        register_skill_tool(self)

    async def _inject_background_notifications(self, messages: list[Message]) -> None:
        """Append system messages for any completed-but-unnotified background tasks."""
        completed = self._bg_manager.get_completed_unnotified()
        for info in completed:
            if info.status == "completed":
                note = f"[Background task {info.task_id} completed] Agent '{info.agent_name}' finished. Use collect_result to retrieve the output."
            elif info.status == "failed":
                note = f"[Background task {info.task_id} failed] Agent '{info.agent_name}' error: {info.error or 'unknown'}"
            else:
                note = f"[Background task {info.task_id} {info.status}] Agent '{info.agent_name}'"
            messages.append(Message(role="system", content=note))
            self._bg_manager.mark_notified(info.task_id)
            await self._emit(
                HookEvent.BACKGROUND_TASK_COMPLETED,
                {
                    "task_id": info.task_id,
                    "agent_name": info.agent_name,
                    "status": info.status,
                    "result": info.result,
                    "error": info.error,
                },
            )

    def _build_system_message(self) -> str:
        from sage.context.message_builder import build_system_message

        return build_system_message(self)

    def _build_messages(self, input: str, memory_context: str | None = None) -> list[Message]:
        from sage.context.message_builder import build_messages

        return build_messages(self, input, memory_context)

    async def _maybe_compact_history(self) -> bool:
        """Compact conversation history when it exceeds the threshold."""
        should_compact = False

        # Use TokenBudget if available (from context: config section).
        if self._token_budget is not None:
            messages = self._build_messages("")
            if self._token_budget.should_compact(messages) and self._turns_since_compaction >= 2:
                should_compact = True
        elif (
            self._context_window_limit is not None
            and self._token_usage > self._context_window_limit * self._token_compaction_threshold
            and self._turns_since_compaction >= 2
        ):
            should_compact = True

        if not should_compact and len(self._conversation_history) > self._compaction_threshold:
            should_compact = True

        if not should_compact:
            self._turns_since_compaction += 1
            self._compacted_last_turn = False
            return False

        before_count = len(self._conversation_history)
        logger.info(
            "Compacting history for agent '%s': %d messages before compaction",
            self.name,
            before_count,
        )
        compacted, strategy = await self._run_compaction_chain(self._conversation_history)
        self._conversation_history = compacted
        self._last_compaction_strategy = strategy
        logger.info(
            "History compacted for agent '%s': %d -> %d messages (strategy: %s)",
            self.name,
            before_count,
            len(self._conversation_history),
            strategy,
        )
        await self._emit(
            HookEvent.ON_COMPACTION,
            {
                "before_count": before_count,
                "after_count": len(self._conversation_history),
                "strategy": strategy,
            },
        )
        self._update_token_usage([message.model_dump() for message in self._build_messages("")])
        self._turns_since_compaction = 0
        self._compacted_last_turn = True
        return True

    async def _run_compaction_chain(self, history: list[Message]) -> tuple[list[Message], str]:
        from sage.memory.compaction import run_compaction_chain

        return await run_compaction_chain(
            history,
            self._compaction_controller,
            self._provider,
            self._compaction_threshold,
        )

    def clear_history(self) -> None:
        """Reset the conversation history for a fresh session."""
        self._conversation_history.clear()
        self._loaded_skills.clear()

    def reset_session(self) -> None:
        """Full session reset: clear history, usage stats, and turn counters."""
        self.clear_history()
        self._cumulative_usage = Usage()
        self._token_usage = 0
        self._compacted_last_turn = False
        self._turns_since_compaction = 0
        self._current_turn = 0

    async def close(self) -> None:
        """Release resources held by the agent (MCP connections, memory DB, etc.).

        Call this when you are finished with the agent to ensure MCP servers
        are disconnected and the memory database connection is closed cleanly.
        Cascades to all subagents.  Safe to call multiple times.
        """
        # Close subagents first so their resources are released before ours.
        for sub in self.subagents.values():
            try:
                await sub.close()
            except (Exception, asyncio.CancelledError) as exc:
                logger.debug("Subagent '%s' close error: %s", sub.name, exc)

        for client in self.mcp_clients:
            try:
                await client.disconnect()
            except Exception as exc:
                logger.debug("MCP disconnect error: %s", exc)
        if self.memory is not None:
            close_memory = cast(
                Callable[[], Awaitable[None]] | None, getattr(self.memory, "close", None)
            )
            if not callable(close_memory):
                return
            try:
                await close_memory()
            except (Exception, asyncio.CancelledError) as exc:
                logger.debug("Memory close error: %s", exc)
            self._memory_initialized = False

    async def _ensure_memory_initialized(self) -> None:
        """Initialize the memory backend on first use (idempotent).

        Calls ``memory.initialize()`` once before the first recall/store
        operation.  Subsequent calls are no-ops.
        """
        if self._memory_initialized or self.memory is None:
            return
        logger.info("Initializing memory for agent '%s'", self.name)
        initialize_memory = cast(
            Callable[[], Awaitable[None]] | None,
            getattr(self.memory, "initialize", None),
        )
        if callable(initialize_memory):
            await initialize_memory()
        self._memory_initialized = True
        logger.info("Memory initialized for agent '%s'", self.name)

    async def _ensure_mcp_initialized(self) -> None:
        """Connect all MCP servers and register their tools (idempotent)."""
        if self._mcp_initialized or not self.mcp_clients:
            return

        # Parallelize initialization: connect all clients concurrently
        async def _initialize_client(client):
            """Initialize a single MCP client and register its tools."""
            try:
                await client.connect()
                schemas = await client.discover_tools()
                logger.info(
                    "Discovered %d MCP tool(s): %s",
                    len(schemas),
                    [s.name for s in schemas],
                )
                for schema in schemas:
                    self.tool_registry.register_mcp_tool(schema, client)
                return None  # Success
            except Exception as exc:
                logger.error("Failed to initialize MCP server %s: %s", client, exc)
                return exc  # Return the exception

        # Run all initializations in parallel
        results = await asyncio.gather(
            *[_initialize_client(client) for client in self.mcp_clients], return_exceptions=True
        )

        # Log any failures (exceptions are already logged above, this just counts them)
        failed_count = sum(1 for r in results if isinstance(r, Exception))
        if failed_count > 0:
            logger.warning(
                "%d of %d MCP client(s) failed to initialize", failed_count, len(self.mcp_clients)
            )

        self._mcp_initialized = True

    async def _recall_memory(self, query: str) -> str | None:
        """Recall relevant memories for the given query, formatted as text."""
        if self.memory is None:
            return None
        logger.debug("Recalling memory for agent '%s': query=%.80s", self.name, query)
        try:
            entries = await self.memory.recall(query)
        except Exception as exc:
            logger.warning("Memory recall failed: %s", exc)
            return None
        if not entries:
            logger.debug("Memory recall for agent '%s': no results", self.name)
            return None
        top_score = entries[0].score if entries[0].score is not None else "N/A"
        logger.debug(
            "Memory recall for agent '%s': %d result(s), top_score=%s",
            self.name,
            len(entries),
            top_score,
        )
        lines = [f"- {e.content}" for e in entries]
        return "\n".join(lines)

    async def _store_memory(self, input: str, output: str) -> None:
        """Persist the exchange to memory, applying configured relevance filters."""
        if self.memory is None:
            return
        content = f"User: {input}\nAssistant: {output}"

        # Apply relevance filter.  When no memory config is present (agent
        # was constructed directly without a config file), fall back to
        # "none" so that the old store-everything behaviour is preserved.
        mem_config = self._memory_config
        relevance_filter = getattr(mem_config, "relevance_filter", "none") if mem_config else "none"
        min_exchange_length = getattr(mem_config, "min_exchange_length", 100) if mem_config else 100
        relevance_threshold = getattr(mem_config, "relevance_threshold", 0.5) if mem_config else 0.5

        if relevance_filter == "length":
            if len(content) < min_exchange_length:
                logger.debug(
                    "Memory store skipped for agent '%s': content too short (%d < %d chars)",
                    self.name,
                    len(content),
                    min_exchange_length,
                )
                return
        elif relevance_filter == "llm":
            score = await self._score_memory_relevance(content)
            storing = score >= relevance_threshold
            logger.debug(
                "Memory relevance score: %.2f (threshold=%.2f, storing=%s)",
                score,
                relevance_threshold,
                storing,
            )
            if not storing:
                return
        # "none": store everything

        try:
            memory_id = await self.memory.store(content)
            logger.debug(
                "Memory stored for agent '%s': id=%s, content_len=%d",
                self.name,
                memory_id,
                len(content),
            )
        except Exception as exc:
            logger.warning("Memory store failed: %s", exc)

    async def _score_memory_relevance(self, content: str) -> float:
        """Ask the provider to score exchange relevance from 0.0 to 1.0."""
        prompt = (
            "Rate the following exchange on a scale from 0.0 to 1.0 based on how "
            "useful it would be to remember for future conversations. "
            "Only output the number, nothing else.\n\n"
            f"{content}"
        )
        try:
            messages = [Message(role="user", content=prompt)]
            result = await self.provider.complete(messages)
            response_text = result.message.content or ""
            return float(response_text.strip())
        except Exception:
            return 1.0  # On any failure, default to storing

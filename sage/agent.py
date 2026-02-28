"""Core agent class that orchestrates LLM calls, tool execution, and memory."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast, overload

from sage.config import AgentConfig, load_config
from sage.hooks.base import HookEvent
from sage.hooks.registry import HookRegistry
from sage.main_config import load_main_config, resolve_and_apply_env, resolve_main_config_path
from sage.tracing import setup_tracing, span

if TYPE_CHECKING:
    from sage.coordination.cancellation import CancellationToken
    from sage.main_config import MainConfig
from sage.exceptions import MaxTurnsExceeded, PermissionError as SagePermissionError, ToolError
from sage.models import CompletionResult, Message, ToolCall, ToolSchema, Usage
from sage.providers.litellm_provider import LiteLLMProvider
from sage.skills.loader import (
    Skill,
    filter_skills_by_names,
    load_skills_from_directory,
    resolve_skills_dir,
)
from sage.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from sage.memory.base import MemoryProtocol
    from sage.mcp.client import MCPClient
    from sage.orchestrator.pipeline import Pipeline
    from sage.providers.base import ProviderProtocol

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _build_hook_registry(
    config: "AgentConfig", memory: "MemoryProtocol | None" = None
) -> "HookRegistry":
    """Build a HookRegistry from agent config, wiring built-in hooks."""
    registry = HookRegistry()

    if config.credential_scrubbing is not None and config.credential_scrubbing.enabled:
        from sage.hooks.builtin.credential_scrubber import make_credential_scrubber

        registry.register(HookEvent.POST_TOOL_EXECUTE, make_credential_scrubber())

    if config.query_classification is not None and config.query_classification.rules:
        from sage.hooks.builtin.query_classifier import ClassificationRule, make_query_classifier

        rules = [
            ClassificationRule(
                keywords=[r.pattern],
                patterns=[],
                priority=r.priority,
                target_model=r.model,
            )
            for r in config.query_classification.rules
        ]
        registry.register(HookEvent.PRE_LLM_CALL, make_query_classifier(rules))

    if config.follow_through is not None and config.follow_through.enabled:
        from sage.hooks.builtin.follow_through import make_follow_through_hook

        registry.register(HookEvent.POST_LLM_CALL, make_follow_through_hook())

    if config.memory is not None and config.memory.auto_load and memory is not None:
        from sage.hooks.builtin.auto_memory import make_auto_memory_hook

        registry.register(
            HookEvent.PRE_LLM_CALL,
            make_auto_memory_hook(memory, max_memories=config.memory.auto_load_top_k),
        )

    return registry


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
        body: str = "",
        model_params: dict[str, Any] | None = None,
        skills: list[Skill] | None = None,
        mcp_clients: list[MCPClient] | None = None,
        compaction_threshold: int = 50,
        parallel_tool_execution: bool = True,
        tool_timeout: float | None = None,
        hook_registry: HookRegistry | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.description = description
        self._body = body
        self.max_turns = max_turns
        self.memory = memory
        self.subagents = subagents or {}
        self.skills: list[Skill] = skills or []
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
        self._last_compaction_strategy: str | None = None

        # Default to LiteLLM provider if none supplied.
        self.provider: ProviderProtocol = provider or LiteLLMProvider(model, **(model_params or {}))  # type: ignore[assignment]

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
        return cls._from_agent_config(config, resolved.parent, global_skills=global_skills)

    @classmethod
    def _from_agent_config(
        cls,
        config: AgentConfig,
        base_dir: Path,
        global_skills: list[Skill] | None = None,
    ) -> Agent:
        """Recursively build an agent (and subagents) from config."""
        global_skills = global_skills or []
        subagents: dict[str, Agent] = {}
        for sub_config in config.subagents:
            subagents[sub_config.name] = cls._from_agent_config(
                sub_config,
                base_dir,
                global_skills=global_skills,
            )

        skills = filter_skills_by_names(global_skills, config.skills)

        # Build MCP clients from config.
        mcp_clients: list[MCPClient] = []
        if config.mcp_servers:
            from sage.mcp.client import MCPClient

            for mcp_cfg in config.mcp_servers.values():
                mcp_clients.append(
                    MCPClient(
                        transport=mcp_cfg.transport,
                        command=mcp_cfg.command,
                        url=mcp_cfg.url,
                        args=mcp_cfg.args,
                        env=mcp_cfg.env,
                    )
                )

        # Build memory backend from config.
        memory: MemoryProtocol | None = None
        if config.memory is not None and config.memory.backend == "sqlite":
            from sage.memory.embedding import LiteLLMEmbedding
            from sage.memory.sqlite_backend import SQLiteMemory

            logger.info(
                "Building memory backend for '%s': backend=%s, embedding=%s, path=%s",
                config.name,
                config.memory.backend,
                config.memory.embedding,
                config.memory.path,
            )
            embedding = LiteLLMEmbedding(config.memory.embedding)
            memory = SQLiteMemory(
                path=config.memory.path, embedding=embedding, config=config.memory
            )
        elif config.memory is not None and config.memory.backend == "file":
            from sage.memory.file_backend import FileMemory

            logger.info(
                "Building file memory backend for '%s': path=%s",
                config.name,
                config.memory.path,
            )
            memory = FileMemory(config.memory.path)

        # Build permission handler from config.
        permission_handler = None
        if config.permission is not None:
            from sage.permissions.base import PermissionAction
            from sage.permissions.policy import CategoryPermissionRule, PolicyPermissionHandler
            from sage.tools.registry import CATEGORY_TOOLS

            rules: list[CategoryPermissionRule] = []
            for category in CATEGORY_TOOLS:
                category_permission = getattr(config.permission, category, None)
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

        # Build token budget from config.
        token_budget = None
        if config.context is not None:
            from sage.context.token_budget import TokenBudget

            try:
                token_budget = TokenBudget(
                    model=config.model,
                    compaction_threshold=config.context.compaction_threshold,
                    reserve_tokens=config.context.reserve_tokens,
                )
            except Exception as exc:
                logger.warning("Failed to create TokenBudget: %s", exc)

        # Build hook registry from config.
        hook_registry = _build_hook_registry(config, memory)

        agent = cls(
            name=config.name,
            model=config.model,
            description=config.description,
            max_turns=config.max_turns,
            subagents=subagents,
            body=config._body,
            model_params=config.model_params.to_kwargs() or None,
            skills=skills or None,
            mcp_clients=mcp_clients or None,
            memory=memory,
            compaction_threshold=config.memory.compaction_threshold
            if config.memory is not None
            else 50,
            parallel_tool_execution=config.parallel_tool_execution,
            tool_timeout=config.tool_timeout,
            hook_registry=hook_registry,
        )

        if config.permission is not None:
            agent.tool_registry.register_from_permissions(
                config.permission,
                extensions=config.extensions or None,
            )
        elif config.extensions:
            for extension_path in config.extensions:
                agent.tool_registry.load_from_module(extension_path)

        # When a semantic memory backend is configured, replace the JSON
        # memory_store / memory_recall tools with closures that delegate to it.
        # This registration happens AFTER register_from_permissions so the
        # semantic versions overwrite any previously registered JSON tools.
        if memory is not None:
            agent._register_memory_tools()

        # Wire permission handler into tool registry.
        if permission_handler is not None:
            agent.tool_registry.set_permission_handler(permission_handler)

        # Wire sandbox: replace the module-level shell tool with a per-agent
        # sandboxed version when sandbox config is present.
        if config.sandbox is not None:
            from sage.tools._sandbox import build_sandbox
            from sage.tools.builtins import make_sandboxed_shell

            sandbox = build_sandbox(config.sandbox)
            sandboxed_shell = make_sandboxed_shell(sandbox)
            agent.tool_registry.register(sandboxed_shell)

        # Store token budget for later use.
        agent._token_budget = token_budget
        agent._git_config = config.git
        agent._memory_config = config.memory

        if config.tracing is not None:
            setup_tracing(config.tracing)

        return agent

    # ── Execution methods ─────────────────────────────────────────────

    @overload
    async def run(self, input: str) -> str: ...

    @overload
    async def run(self, input: str, *, response_model: type[T]) -> T: ...

    async def run(self, input: str, *, response_model: type[T] | None = None) -> str | T:
        """Main execution loop: LLM call -> tool execution -> repeat until done.

        The loop runs for at most ``max_turns`` iterations.  Each iteration
        calls the provider, checks for tool calls in the response, executes
        them, and feeds the results back.  The loop terminates when the model
        produces a response with no tool calls or ``max_turns`` is exceeded.

        Conversation history is accumulated across calls so that subsequent
        invocations see the full multi-turn context.

        MCP servers are connected on first call and their tools are registered
        into the tool registry.  Memory is recalled before the first turn and
        persisted after the final response.

        When ``response_model`` is provided (a Pydantic model class), a system
        message is injected instructing the LLM to respond with JSON matching
        the model's schema.  The final output is then parsed and returned as an
        instance of that model instead of a raw string.
        """
        logger.info("Agent '%s' run started: %s", self.name, input[:80])

        messages = await self._pre_loop_setup(input)

        async with span("agent.run", {"agent.name": self.name, "model": self.model}) as agent_span:
            if response_model is not None:
                schema = response_model.model_json_schema()  # type: ignore[attr-defined]
                schema_instruction = Message(
                    role="system",
                    content=f"Respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}",
                )
                # Insert after any existing system messages, before the first non-system message.
                insert_idx = next(
                    (i for i, m in enumerate(messages) if m.role != "system"),
                    len(messages),
                )
                messages.insert(insert_idx, schema_instruction)

            for turn in range(self.max_turns):
                logger.debug("Turn %d/%d", turn + 1, self.max_turns)
                tool_schemas = self.tool_registry.get_schemas() or None
                await self._emit(
                    HookEvent.PRE_LLM_CALL,
                    {"model": self.model, "messages": messages, "tool_schemas": tool_schemas},
                )
                result: CompletionResult = await self.provider.complete(
                    messages, tools=tool_schemas
                )
                self._cumulative_usage += result.usage
                await self._emit(HookEvent.POST_LLM_CALL, {"result": result, "turn": turn})

                messages.append(result.message)

                # No tool calls means the model is done.
                if not result.message.tool_calls:
                    logger.info("Agent '%s' run complete after %d turn(s)", self.name, turn + 1)
                    final_output = result.message.content or ""
                    agent_span.set_attribute("turn_count", turn + 1)
                    await self._post_loop_cleanup(input, final_output)
                    if response_model is not None:
                        # Strip markdown code fences that some LLMs wrap around JSON.
                        cleaned = re.sub(
                            r"^```(?:json)?\n?|```$", "", final_output.strip(), flags=re.MULTILINE
                        ).strip()
                        return response_model.model_validate_json(cleaned)  # type: ignore[attr-defined, no-any-return]
                    return final_output

                await self._execute_tool_calls(result.message.tool_calls, messages)

            # Max turns exceeded — persist partial progress, then raise.
            logger.warning("Agent '%s' reached max_turns (%d)", self.name, self.max_turns)
            agent_span.set_attribute("turn_count", self.max_turns)
            last_content = self._extract_final_output(messages)
            if last_content:
                await self._store_memory(input, last_content)
            raise MaxTurnsExceeded(turns=self.max_turns, last_content=last_content)

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
                logger.debug("Stream turn %d/%d", turn + 1, self.max_turns)
                tool_schemas = self.tool_registry.get_schemas() or None
                await self._emit(
                    HookEvent.PRE_LLM_CALL,
                    {"model": self.model, "messages": messages, "tool_schemas": tool_schemas},
                )

                # Accumulate the full assistant content and tool calls for this turn.
                turn_content = ""
                turn_tool_calls: list[ToolCall] | None = None
                turn_usage: Usage | None = None

                async for chunk in self.provider.stream(messages, tools=tool_schemas):  # type: ignore[attr-defined]
                    if chunk.delta:
                        turn_content += chunk.delta
                        yield chunk.delta
                    if chunk.tool_calls:
                        turn_tool_calls = chunk.tool_calls
                    if chunk.usage is not None:
                        turn_usage = chunk.usage

                if turn_usage is not None:
                    self._cumulative_usage += turn_usage

                # Build the assistant message for the conversation history.
                assistant_msg = Message(
                    role="assistant",
                    content=turn_content or None,
                    tool_calls=turn_tool_calls,
                )
                messages.append(assistant_msg)
                await self._emit(
                    HookEvent.POST_LLM_CALL,
                    {"result": assistant_msg, "turn": turn},
                )

                # No tool calls means the model is done.
                if not turn_tool_calls:
                    logger.info(
                        "Agent '%s' stream complete after %d turn(s)",
                        self.name,
                        turn + 1,
                    )
                    agent_span.set_attribute("turn_count", turn + 1)
                    await self._post_loop_cleanup(input, turn_content)
                    return

                await self._execute_tool_calls(turn_tool_calls, messages)

            # Max turns exceeded — persist partial progress, then raise.
            logger.warning(
                "Agent '%s' reached max_turns (%d) during stream", self.name, self.max_turns
            )
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

    async def delegate(self, subagent_name: str, task: str) -> str:
        """Delegate a task to a named subagent.

        Raises:
            ToolError: If the subagent name is not found.
        """
        if subagent_name not in self.subagents:
            raise ToolError(f"Unknown subagent: {subagent_name}")
        logger.debug(
            "Delegating to subagent '%s': %s",
            subagent_name,
            task[:120],
        )
        await self._emit(HookEvent.ON_DELEGATION, {"target": subagent_name, "input": task})
        subagent = self.subagents[subagent_name]
        try:
            result = await subagent.run(task)
        except KeyboardInterrupt:
            raise  # Always propagate user interrupts
        except BaseException as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            logger.error("Subagent '%s' crashed: %s", subagent.name, e, exc_info=True)
            result = f"[Subagent Error] {subagent.name} failed: {type(e).__name__}: {e}"
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

        # Build a quick lookup for skill-name matching.
        skill_names = {s.name for s in self.skills}

        async def _safe_execute(tc: ToolCall) -> tuple[str, str]:
            # Log whether this tool dispatch is skill-driven.
            if tc.name == "delegate":
                # Delegation is logged inside delegate(); skip here.
                pass
            elif tc.name == "shell" and skill_names:
                cmd = (tc.arguments or {}).get("command", "")
                matched = [sn for sn in skill_names if sn in cmd]
                if matched:
                    logger.debug(
                        "Delegating to skill '%s' via shell: %s",
                        matched[0],
                        cmd[:120],
                    )
                else:
                    logger.debug("Executing tool '%s': %s", tc.name, str(tc.arguments)[:120])
            else:
                logger.debug("Executing tool '%s': %s", tc.name, str(tc.arguments)[:120])

            try:
                result = await self.tool_registry.execute(tc.name, tc.arguments or {})
                result_str = str(result)
                await self._emit(
                    HookEvent.POST_TOOL_EXECUTE,
                    {"tool_name": tc.name, "arguments": tc.arguments or {}, "result": result_str},
                )
                return tc.id, result_str
            except SagePermissionError:
                raise  # Never swallow permission errors — re-raise so the agent loop can handle them
            except ToolError as exc:
                logger.error("Tool '%s' failed: %s", tc.name, exc)
                return tc.id, f"Error executing tool '{tc.name}': {exc}"
            except Exception as exc:
                logger.error("Tool '%s' raised unexpected error: %s", tc.name, exc)
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
        """Register a ``delegate`` tool so the LLM can invoke subagents.

        Creates an async callable that wraps :meth:`delegate` and attaches
        the appropriate :class:`ToolSchema` so the tool registry can
        advertise it to the LLM and dispatch calls to it.
        """
        subagent_names = list(self.subagents.keys())
        description_lines = [
            "Delegate a task to a subagent and return its response.",
            "",
            "Available subagents:",
        ]
        for name in subagent_names:
            sub = self.subagents[name]
            desc = sub.description or "(no description)"
            description_lines.append(f"  - {name}: {desc}")

        # Capture self via closure for the tool function.
        agent_ref = self

        async def delegate(agent_name: str, task: str) -> str:  # noqa: D401
            return await agent_ref.delegate(agent_name, task)

        schema = ToolSchema(
            name="delegate",
            description="\n".join(description_lines),
            parameters={
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": f"Name of the subagent. One of: {subagent_names}",
                        "enum": subagent_names,
                    },
                    "task": {
                        "type": "string",
                        "description": "The task or input to send to the subagent.",
                    },
                },
                "required": ["agent_name", "task"],
            },
        )
        delegate.__tool_schema__ = schema  # type: ignore[attr-defined]
        self.tool_registry.register(delegate)

    def _register_memory_tools(self) -> None:
        """Register memory_store, memory_recall, and memory_forget tool closures.

        Only called when ``self.memory`` is not None.
        """
        if self.memory is None:
            return

        from sage.tools.decorator import tool as _tool

        memory_ref = self.memory

        @_tool
        async def memory_store(key: str, value: str) -> str:
            """Store a key-value pair in the agent's semantic memory backend."""
            await memory_ref.store(f"{key}: {value}", metadata={"key": key})
            return f"Stored: {key}"

        @_tool
        async def memory_recall(query: str) -> str:
            """Recall entries from the agent's semantic memory backend."""
            entries = await memory_ref.recall(query)
            if not entries:
                return f"No matches for: {query}"
            return "\n".join(f"- {e.content}" for e in entries)

        @_tool
        async def memory_forget(memory_id: str) -> str:
            """Forget/delete a specific memory entry by its ID."""
            result = await memory_ref.forget(memory_id)
            return f"Memory {memory_id} {'deleted' if result else 'not found'}"

        self.tool_registry.register(memory_store)
        self.tool_registry.register(memory_recall)
        self.tool_registry.register(memory_forget)

    def _build_messages(self, input: str, memory_context: str | None = None) -> list[Message]:
        """Build the full message list including conversation history.

        The returned list contains, in order:
          1. System messages (body + skills)
          2. Memory-context system message (if any)
          3. Prior conversation history (user/assistant turns)
          4. The new user message
        """
        messages: list[Message] = []

        # System message from description/body + skills.
        system_parts: list[str] = []
        if self._body:
            system_parts.append(self._body)
        for skill in self.skills:
            header = f"## Skill: {skill.name}"
            if skill.description:
                header += f"\n_{skill.description}_"
            system_parts.append(f"{header}\n\n{skill.content}")
        if system_parts:
            messages.append(Message(role="system", content="\n\n".join(system_parts)))

        # Prepend recalled memory as a system-level context block.
        if memory_context:
            messages.append(Message(role="system", content=f"[Relevant memory]\n{memory_context}"))

        # Insert prior conversation turns.
        messages.extend(self._conversation_history)

        messages.append(Message(role="user", content=input))
        return messages

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
        """Try LLM summarization, fall back to emergency_drop, then deterministic_trim.

        Returns (compacted_history, strategy_name).
        """
        from sage.memory.compaction import (
            compact_messages,
            deterministic_trim,
            emergency_drop,
        )

        # Strategy 1: LLM summarization via compact_messages (with correct threshold)
        try:
            result = await compact_messages(
                history,
                self.provider,
                threshold=self._compaction_threshold,
                keep_recent=10,
            )
            if len(result) < len(history):
                return result, "compact_messages"
        except Exception as exc:
            logger.warning("compact_messages failed, falling back to emergency_drop: %s", exc)

        # Strategy 2: emergency drop (preserves system/last-user/tool results)
        try:
            result = emergency_drop(history)
            if len(result) < len(history):
                return result, "emergency_drop"
        except Exception as exc:
            logger.warning("emergency_drop failed, falling back to deterministic_trim: %s", exc)

        # Strategy 3: deterministic trim (always succeeds)
        result = deterministic_trim(history, target_count=self._compaction_threshold)
        return result, "deterministic_trim"

    def clear_history(self) -> None:
        """Reset the conversation history for a fresh session."""
        self._conversation_history.clear()

    async def close(self) -> None:
        """Release resources held by the agent (MCP connections, memory DB, etc.).

        Call this when you are finished with the agent to ensure MCP servers
        are disconnected and the memory database connection is closed cleanly.
        Safe to call multiple times.
        """
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

        for client in self.mcp_clients:
            try:
                await client.connect()
                schemas = await client.discover_tools()
                logger.info(
                    "MCP server connected, discovered %d tool(s): %s",
                    len(schemas),
                    [s.name for s in schemas],
                )
                for schema in schemas:
                    self.tool_registry.register_mcp_tool(schema, client)
            except Exception as exc:
                logger.error("Failed to initialize MCP server: %s", exc)

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

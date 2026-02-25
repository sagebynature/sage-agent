"""Core agent class that orchestrates LLM calls, tool execution, and memory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sage.config import AgentConfig, load_config

if TYPE_CHECKING:
    from sage.main_config import MainConfig
from sage.exceptions import ToolError
from sage.models import CompletionResult, Message, ToolCall, ToolSchema
from sage.providers.litellm_provider import LiteLLMProvider
from sage.skills.loader import Skill, load_skills_from_directory
from sage.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from sage.memory.base import MemoryProtocol
    from sage.mcp.client import MCPClient
    from sage.orchestrator.pipeline import Pipeline
    from sage.providers.base import ProviderProtocol

logger = logging.getLogger(__name__)


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
        self._context_window_limit: int | None = None
        self._token_compaction_threshold: float = 0.8
        self._turns_since_compaction: int = 0
        self._context_window_detected: bool = False
        self._compacted_last_turn: bool = False
        self._token_budget: Any | None = None

        # Default to LiteLLM provider if none supplied.
        self.provider: ProviderProtocol = provider or LiteLLMProvider(model, **(model_params or {}))  # type: ignore[assignment]

        # Build tool registry from the supplied tool list.
        self.tool_registry = ToolRegistry()
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
        config = load_config(str(resolved), central=central)
        return cls._from_agent_config(config, resolved.parent)

    @classmethod
    def _from_agent_config(cls, config: AgentConfig, base_dir: Path) -> Agent:
        """Recursively build an agent (and subagents) from config."""
        subagents: dict[str, Agent] = {}
        for sub_config in config.subagents:
            subagents[sub_config.name] = cls._from_agent_config(sub_config, base_dir)

        # Resolve skills directory: explicit config takes priority, otherwise
        # auto-discover a "skills/" directory next to the config file.
        if config.skills_dir is not None:
            resolved_skills_dir = base_dir / config.skills_dir
            skills = load_skills_from_directory(resolved_skills_dir)
        else:
            default_skills_dir = base_dir / "skills"
            skills = (
                load_skills_from_directory(default_skills_dir)
                if default_skills_dir.is_dir()
                else []
            )

        # Build MCP clients from config.
        mcp_clients: list[MCPClient] = []
        if config.mcp_servers:
            from sage.mcp.client import MCPClient

            for mcp_cfg in config.mcp_servers:
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
            memory = SQLiteMemory(path=config.memory.path, embedding=embedding)

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
        )

        if config.permission is not None:
            agent.tool_registry.register_from_permissions(
                config.permission,
                extensions=config.extensions or None,
            )
        elif config.extensions:
            for extension_path in config.extensions:
                agent.tool_registry.load_from_module(extension_path)

        # Wire permission handler into tool registry.
        if permission_handler is not None:
            agent.tool_registry.set_permission_handler(permission_handler)

        # Store token budget for later use.
        agent._token_budget = token_budget

        return agent

    # ── Execution methods ─────────────────────────────────────────────

    async def run(self, input: str) -> str:
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
        """
        logger.info("Agent '%s' run started: %s", self.name, input[:80])

        # Connect MCP servers and register their tools on first run.
        await self._ensure_mcp_initialized()
        await self._ensure_memory_initialized()
        if not self._context_window_detected:
            self._detect_context_window_limit()

        # Recall relevant memories and prepend as context.
        memory_context = await self._recall_memory(input)

        messages = self._build_messages(input, memory_context=memory_context)

        final_output = ""

        for turn in range(self.max_turns):
            logger.debug("Turn %d/%d", turn + 1, self.max_turns)
            tool_schemas = self.tool_registry.get_schemas() or None
            result: CompletionResult = await self.provider.complete(messages, tools=tool_schemas)

            messages.append(result.message)

            # No tool calls means the model is done.
            if not result.message.tool_calls:
                logger.info("Agent '%s' run complete after %d turn(s)", self.name, turn + 1)
                final_output = result.message.content or ""
                # Persist the user + assistant exchange to conversation history.
                self._conversation_history.append(Message(role="user", content=input))
                self._conversation_history.append(Message(role="assistant", content=final_output))
                compacted = await self._maybe_compact_history()
                _ = compacted
                self._update_token_usage(
                    [message.model_dump() for message in self._build_messages("")]
                )
                await self._store_memory(input, final_output)
                return final_output

            # Execute each tool call and append results.
            tool_names = [tc.name for tc in result.message.tool_calls]
            logger.debug("Dispatching tools: %s", tool_names)

            # Build a quick lookup for skill-name matching.
            skill_names = {s.name for s in self.skills}

            for tc in result.message.tool_calls:
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
                    tool_result = await self._execute_tool(tc)
                except Exception as e:
                    logger.error("Tool '%s' failed: %s", tc.name, e)
                    tool_result = f"Error executing tool '{tc.name}': {e}"

                messages.append(
                    Message(
                        role="tool",
                        content=str(tool_result),
                        tool_call_id=tc.id,
                    )
                )

        # Max turns exceeded — return last assistant content.
        logger.warning("Agent '%s' reached max_turns (%d)", self.name, self.max_turns)
        for msg in reversed(messages):
            if msg.role == "assistant" and msg.content:
                final_output = msg.content
                self._conversation_history.append(Message(role="user", content=input))
                self._conversation_history.append(Message(role="assistant", content=final_output))
                compacted = await self._maybe_compact_history()
                _ = compacted
                self._update_token_usage(
                    [message.model_dump() for message in self._build_messages("")]
                )
                await self._store_memory(input, final_output)
                return final_output
        return ""

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

        await self._ensure_mcp_initialized()
        await self._ensure_memory_initialized()
        if not self._context_window_detected:
            self._detect_context_window_limit()

        memory_context = await self._recall_memory(input)
        messages = self._build_messages(input, memory_context=memory_context)

        for turn in range(self.max_turns):
            logger.debug("Stream turn %d/%d", turn + 1, self.max_turns)
            tool_schemas = self.tool_registry.get_schemas() or None

            # Accumulate the full assistant content and tool calls for this turn.
            turn_content = ""
            turn_tool_calls: list[ToolCall] | None = None

            async for chunk in self.provider.stream(messages, tools=tool_schemas):  # type: ignore[attr-defined]
                if chunk.delta:
                    turn_content += chunk.delta
                    yield chunk.delta
                if chunk.tool_calls:
                    turn_tool_calls = chunk.tool_calls

            # Build the assistant message for the conversation history.
            assistant_msg = Message(
                role="assistant",
                content=turn_content or None,
                tool_calls=turn_tool_calls,
            )
            messages.append(assistant_msg)

            # No tool calls means the model is done.
            if not turn_tool_calls:
                logger.info(
                    "Agent '%s' stream complete after %d turn(s)",
                    self.name,
                    turn + 1,
                )
                self._conversation_history.append(Message(role="user", content=input))
                self._conversation_history.append(Message(role="assistant", content=turn_content))
                compacted = await self._maybe_compact_history()
                _ = compacted
                self._update_token_usage(
                    [message.model_dump() for message in self._build_messages("")]
                )
                await self._store_memory(input, turn_content)
                return

            # Execute each tool call and append results.
            tool_names = [tc.name for tc in turn_tool_calls]
            logger.debug("Dispatching tools: %s", tool_names)

            for tc in turn_tool_calls:
                try:
                    tool_result = await self._execute_tool(tc)
                except Exception as e:
                    logger.error("Tool '%s' failed: %s", tc.name, e)
                    tool_result = f"Error executing tool '{tc.name}': {e}"

                messages.append(
                    Message(
                        role="tool",
                        content=str(tool_result),
                        tool_call_id=tc.id,
                    )
                )

        # Max turns exceeded — find last assistant content.
        logger.warning("Agent '%s' reached max_turns (%d) during stream", self.name, self.max_turns)
        for msg in reversed(messages):
            if msg.role == "assistant" and msg.content:
                self._conversation_history.append(Message(role="user", content=input))
                self._conversation_history.append(Message(role="assistant", content=msg.content))
                compacted = await self._maybe_compact_history()
                _ = compacted
                self._update_token_usage(
                    [message.model_dump() for message in self._build_messages("")]
                )
                await self._store_memory(input, msg.content)
                return

    def _detect_context_window_limit(self) -> None:
        if self._context_window_detected:
            return

        self._context_window_detected = True
        self._context_window_limit = None

        try:
            import litellm

            model_info = litellm.get_model_info(self.model)
            max_input_tokens = model_info.get("max_input_tokens")
            if isinstance(max_input_tokens, int):
                self._context_window_limit = max_input_tokens
            elif isinstance(max_input_tokens, float):
                self._context_window_limit = int(max_input_tokens)
        except Exception:
            self._context_window_limit = None

    def _update_token_usage(self, messages: list[dict[str, Any]]) -> None:
        try:
            import litellm

            self._token_usage = int(litellm.token_counter(model=self.model, messages=messages))
        except Exception:
            self._token_usage = 0

    def get_usage_stats(self) -> dict[str, int | float | bool | None]:
        usage_percentage: float | None = None
        if self._context_window_limit and self._context_window_limit > 0:
            usage_percentage = min(1.0, self._token_usage / self._context_window_limit)

        return {
            "token_usage": self._token_usage,
            "context_window_limit": self._context_window_limit,
            "usage_percentage": usage_percentage,
            "compacted_this_turn": self._compacted_last_turn,
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
        return await self.subagents[subagent_name].run(task)

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

        from sage.memory.compaction import compact_messages

        before_count = len(self._conversation_history)
        logger.info(
            "Compacting history for agent '%s': %d messages before compaction",
            self.name,
            before_count,
        )
        self._conversation_history = await compact_messages(
            self._conversation_history,
            self.provider,
            threshold=self._compaction_threshold,
            keep_recent=10,
        )
        logger.info(
            "History compacted for agent '%s': %d -> %d messages",
            self.name,
            before_count,
            len(self._conversation_history),
        )
        self._update_token_usage([message.model_dump() for message in self._build_messages("")])
        self._turns_since_compaction = 0
        self._compacted_last_turn = True
        return True

    def clear_history(self) -> None:
        """Reset the conversation history for a fresh session."""
        self._conversation_history.clear()

    def _build_initial_messages(
        self, input: str, memory_context: str | None = None
    ) -> list[Message]:
        """Build the initial message list with system prompt and user input."""
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

        messages.append(Message(role="user", content=input))
        return messages

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
        if self.memory is not None and hasattr(self.memory, "close"):
            await self.memory.close()
            self._memory_initialized = False

    async def _ensure_memory_initialized(self) -> None:
        """Initialize the memory backend on first use (idempotent).

        Calls ``memory.initialize()`` once before the first recall/store
        operation.  Subsequent calls are no-ops.
        """
        if self._memory_initialized or self.memory is None:
            return
        logger.info("Initializing memory for agent '%s'", self.name)
        if hasattr(self.memory, "initialize"):
            await self.memory.initialize()
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

    async def _execute_tool(self, tc: ToolCall) -> str:
        """Dispatch a tool call through the registry."""
        return await self.tool_registry.execute(tc.name, tc.arguments)

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
        """Persist the exchange to memory."""
        if self.memory is None:
            return
        content = f"User: {input}\nAssistant: {output}"
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

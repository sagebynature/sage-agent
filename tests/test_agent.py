"""Tests for the Agent class — core orchestration of LLM calls and tool execution."""

from __future__ import annotations

import logging
import textwrap
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from sage.agent import Agent
from sage.exceptions import ToolError
from sage.models import (
    CompletionResult,
    Message,
    StreamChunk,
    ToolCall,
    ToolSchema,
    Usage,
)
from sage.tools.decorator import tool


# ── Mock Provider ─────────────────────────────────────────────────────


class MockProvider:
    """Mock provider that returns predetermined CompletionResult responses."""

    def __init__(self, responses: list[CompletionResult]) -> None:
        self.responses = list(responses)
        self.call_count = 0
        self.call_args: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: Any,
    ) -> CompletionResult:
        self.call_args.append({"messages": list(messages), "tools": tools})
        result = self.responses[self.call_count]
        self.call_count += 1
        return result

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        self.call_args.append({"messages": list(messages), "tools": tools})
        result = self.responses[self.call_count]
        self.call_count += 1
        if result.message.content:
            for char in result.message.content:
                yield StreamChunk(delta=char)
        if result.message.tool_calls:
            yield StreamChunk(finish_reason="tool_calls", tool_calls=result.message.tool_calls)
        else:
            yield StreamChunk(finish_reason="stop")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


# ── Helper to build CompletionResults ─────────────────────────────────


def _text_result(content: str) -> CompletionResult:
    """Create a CompletionResult with a plain text assistant message."""
    return CompletionResult(
        message=Message(role="assistant", content=content),
        usage=Usage(),
    )


def _tool_call_result(tool_calls: list[ToolCall], content: str | None = None) -> CompletionResult:
    """Create a CompletionResult with tool calls."""
    return CompletionResult(
        message=Message(role="assistant", content=content, tool_calls=tool_calls),
        usage=Usage(),
    )


# ── Sample tools for testing ──────────────────────────────────────────


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"


@tool
def failing_tool() -> str:
    """A tool that always fails."""
    raise RuntimeError("Something went wrong")


# ── Tests ─────────────────────────────────────────────────────────────


class TestAgentRun:
    """Tests for Agent.run — the main execution loop."""

    @pytest.mark.asyncio
    async def test_basic_run(self) -> None:
        """Simple question → single text response with no tool calls."""
        provider = MockProvider([_text_result("The answer is 42.")])
        agent = Agent(name="test", model="test-model", provider=provider)

        result = await agent.run("What is the meaning of life?")

        assert result == "The answer is 42."
        assert provider.call_count == 1

    @pytest.mark.asyncio
    async def test_run_with_tool_loop(self) -> None:
        """Query triggers a tool call, tool result feeds back, final text response."""
        tool_calls = [ToolCall(id="tc_1", name="add", arguments={"a": 2, "b": 3})]
        provider = MockProvider(
            [
                _tool_call_result(tool_calls),
                _text_result("2 + 3 = 5"),
            ]
        )
        agent = Agent(name="calc", model="test-model", tools=[add], provider=provider)

        result = await agent.run("What is 2 + 3?")

        assert result == "2 + 3 = 5"
        assert provider.call_count == 2

        # Verify the tool result message was appended.
        second_call_messages = provider.call_args[1]["messages"]
        tool_msgs = [m for m in second_call_messages if m.role == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].content == "5"
        assert tool_msgs[0].tool_call_id == "tc_1"

    @pytest.mark.asyncio
    async def test_run_max_turns_exceeded(self) -> None:
        """Agent raises MaxTurnsExceeded when max_turns is exhausted."""
        from sage.exceptions import MaxTurnsExceeded

        tool_calls = [ToolCall(id="tc_loop", name="add", arguments={"a": 1, "b": 1})]
        responses = [_tool_call_result(tool_calls, content="still thinking...") for _ in range(3)]
        provider = MockProvider(responses)
        agent = Agent(
            name="stuck",
            model="test-model",
            tools=[add],
            provider=provider,
            max_turns=3,
        )

        with pytest.raises(MaxTurnsExceeded) as exc_info:
            await agent.run("Loop forever")

        assert exc_info.value.turns == 3
        assert exc_info.value.last_content == "still thinking..."
        assert provider.call_count == 3

    @pytest.mark.asyncio
    async def test_run_max_turns_no_content(self) -> None:
        """MaxTurnsExceeded carries empty last_content when there was no text."""
        from sage.exceptions import MaxTurnsExceeded

        tool_calls = [ToolCall(id="tc_x", name="add", arguments={"a": 0, "b": 0})]
        responses = [_tool_call_result(tool_calls, content=None) for _ in range(2)]
        provider = MockProvider(responses)
        agent = Agent(
            name="empty",
            model="test-model",
            tools=[add],
            provider=provider,
            max_turns=2,
        )

        with pytest.raises(MaxTurnsExceeded) as exc_info:
            await agent.run("No content")

        assert exc_info.value.turns == 2
        assert exc_info.value.last_content == ""

    @pytest.mark.asyncio
    async def test_run_tool_error_handled(self) -> None:
        """Tool exception is caught and error message is passed back to the LLM."""
        tool_calls = [ToolCall(id="tc_fail", name="failing_tool", arguments={})]
        provider = MockProvider(
            [
                _tool_call_result(tool_calls),
                _text_result("The tool failed, sorry."),
            ]
        )
        agent = Agent(
            name="error-agent",
            model="test-model",
            tools=[failing_tool],
            provider=provider,
        )

        result = await agent.run("Do the thing")

        assert result == "The tool failed, sorry."

        # Check that the error message was passed as a tool result.
        second_call_messages = provider.call_args[1]["messages"]
        tool_msgs = [m for m in second_call_messages if m.role == "tool"]
        assert len(tool_msgs) == 1
        assert "Error executing tool 'failing_tool'" in tool_msgs[0].content
        assert "Something went wrong" in tool_msgs[0].content

    @pytest.mark.asyncio
    async def test_run_multiple_tool_calls(self) -> None:
        """Multiple tool calls in a single response are all executed."""
        tool_calls = [
            ToolCall(id="tc_a", name="add", arguments={"a": 1, "b": 2}),
            ToolCall(id="tc_b", name="greet", arguments={"name": "World"}),
        ]
        provider = MockProvider(
            [
                _tool_call_result(tool_calls),
                _text_result("Done: 3 and Hello, World!"),
            ]
        )
        agent = Agent(
            name="multi",
            model="test-model",
            tools=[add, greet],
            provider=provider,
        )

        result = await agent.run("Add 1+2 and greet World")

        assert result == "Done: 3 and Hello, World!"
        second_call_messages = provider.call_args[1]["messages"]
        tool_msgs = [m for m in second_call_messages if m.role == "tool"]
        assert len(tool_msgs) == 2
        assert tool_msgs[0].content == "3"
        assert tool_msgs[1].content == "Hello, World!"


class TestAgentStream:
    """Tests for Agent.stream — streaming text output."""

    @pytest.mark.asyncio
    async def test_stream_basic(self) -> None:
        """Verify streaming yields individual content chunks."""
        provider = MockProvider([_text_result("Hello!")])
        agent = Agent(name="streamer", model="test-model", provider=provider)

        chunks: list[str] = []
        async for chunk in agent.stream("Say hello"):
            chunks.append(chunk)

        # Each character of "Hello!" plus no extra from finish_reason chunk.
        assert "".join(chunks) == "Hello!"
        assert len(chunks) == len("Hello!")

    @pytest.mark.asyncio
    async def test_stream_empty_response(self) -> None:
        """Streaming an empty response yields nothing."""
        provider = MockProvider([_text_result("")])
        agent = Agent(name="empty-stream", model="test-model", provider=provider)

        chunks: list[str] = []
        async for chunk in agent.stream("Say nothing"):
            chunks.append(chunk)

        assert chunks == []


class TestAgentStreamWithTools:
    """Tests for Agent.stream — streaming with tool call loop support."""

    @pytest.mark.asyncio
    async def test_stream_with_tool_loop(self) -> None:
        """Stream with a single tool call loop: tool call → result → text."""
        tool_calls = [ToolCall(id="tc_1", name="add", arguments={"a": 2, "b": 3})]
        provider = MockProvider(
            [
                _tool_call_result(tool_calls),
                _text_result("2 + 3 = 5"),
            ]
        )
        agent = Agent(name="stream-calc", model="test-model", tools=[add], provider=provider)

        chunks: list[str] = []
        async for chunk in agent.stream("What is 2 + 3?"):
            chunks.append(chunk)

        full_text = "".join(chunks)
        assert full_text == "2 + 3 = 5"
        assert provider.call_count == 2

        # Verify tool result was passed back in second call.
        second_call_messages = provider.call_args[1]["messages"]
        tool_msgs = [m for m in second_call_messages if m.role == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].content == "5"
        assert tool_msgs[0].tool_call_id == "tc_1"

    @pytest.mark.asyncio
    async def test_stream_with_multiple_tool_calls(self) -> None:
        """Stream with multiple tool calls in a single turn."""
        tool_calls = [
            ToolCall(id="tc_a", name="add", arguments={"a": 1, "b": 2}),
            ToolCall(id="tc_b", name="greet", arguments={"name": "World"}),
        ]
        provider = MockProvider(
            [
                _tool_call_result(tool_calls),
                _text_result("Done: 3 and Hello, World!"),
            ]
        )
        agent = Agent(
            name="stream-multi",
            model="test-model",
            tools=[add, greet],
            provider=provider,
        )

        chunks: list[str] = []
        async for chunk in agent.stream("Add 1+2 and greet World"):
            chunks.append(chunk)

        full_text = "".join(chunks)
        assert full_text == "Done: 3 and Hello, World!"

        second_call_messages = provider.call_args[1]["messages"]
        tool_msgs = [m for m in second_call_messages if m.role == "tool"]
        assert len(tool_msgs) == 2
        assert tool_msgs[0].content == "3"
        assert tool_msgs[1].content == "Hello, World!"

    @pytest.mark.asyncio
    async def test_stream_with_tool_error(self) -> None:
        """Stream handles tool execution errors gracefully."""
        tool_calls = [ToolCall(id="tc_fail", name="failing_tool", arguments={})]
        provider = MockProvider(
            [
                _tool_call_result(tool_calls),
                _text_result("The tool failed, sorry."),
            ]
        )
        agent = Agent(
            name="stream-error",
            model="test-model",
            tools=[failing_tool],
            provider=provider,
        )

        chunks: list[str] = []
        async for chunk in agent.stream("Do the thing"):
            chunks.append(chunk)

        full_text = "".join(chunks)
        assert full_text == "The tool failed, sorry."

        # Verify error message was passed as tool result.
        second_call_messages = provider.call_args[1]["messages"]
        tool_msgs = [m for m in second_call_messages if m.role == "tool"]
        assert len(tool_msgs) == 1
        assert "Error executing tool 'failing_tool'" in tool_msgs[0].content
        assert "Something went wrong" in tool_msgs[0].content

    @pytest.mark.asyncio
    async def test_stream_max_turns_exceeded(self) -> None:
        """Stream raises MaxTurnsExceeded when max_turns is exhausted."""
        from sage.exceptions import MaxTurnsExceeded

        tool_calls = [ToolCall(id="tc_loop", name="add", arguments={"a": 1, "b": 1})]
        responses = [_tool_call_result(tool_calls, content="still thinking...") for _ in range(3)]
        provider = MockProvider(responses)
        agent = Agent(
            name="stream-stuck",
            model="test-model",
            tools=[add],
            provider=provider,
            max_turns=3,
        )

        with pytest.raises(MaxTurnsExceeded) as exc_info:
            async for _ in agent.stream("Loop forever"):
                pass

        assert exc_info.value.turns == 3
        assert exc_info.value.last_content == "still thinking..."
        assert provider.call_count == 3

    @pytest.mark.asyncio
    async def test_stream_with_memory(self) -> None:
        """Stream integrates with memory recall and store."""
        from unittest.mock import AsyncMock

        from sage.memory.base import MemoryEntry

        mock_memory = AsyncMock()
        mock_memory.initialize = AsyncMock()
        mock_memory.recall = AsyncMock(
            return_value=[
                MemoryEntry(id="1", content="Paris is the capital of France."),
            ]
        )
        mock_memory.store = AsyncMock()

        provider = MockProvider([_text_result("Paris")])
        agent = Agent(
            name="stream-mem",
            model="test-model",
            provider=provider,
            memory=mock_memory,
        )

        chunks: list[str] = []
        async for chunk in agent.stream("What is the capital of France?"):
            chunks.append(chunk)

        full_text = "".join(chunks)
        assert full_text == "Paris"

        # Memory was recalled and stored.
        mock_memory.recall.assert_awaited_once_with("What is the capital of France?")
        mock_memory.store.assert_awaited_once()
        stored_content = mock_memory.store.call_args[0][0]
        assert "What is the capital of France?" in stored_content
        assert "Paris" in stored_content


class TestAgentDelegate:
    """Tests for Agent.delegate — subagent delegation."""

    @pytest.mark.asyncio
    async def test_delegate_to_subagent(self) -> None:
        """Delegate a task to a named subagent and get its result."""
        sub_provider = MockProvider([_text_result("Subagent result")])
        subagent = Agent(name="helper", model="test-model", provider=sub_provider)

        main_provider = MockProvider([_text_result("Main result")])
        agent = Agent(
            name="main",
            model="test-model",
            provider=main_provider,
            subagents={"helper": subagent},
        )

        result = await agent.delegate("helper", "Do something")
        assert result == "Subagent result"
        assert sub_provider.call_count == 1

    @pytest.mark.asyncio
    async def test_delegate_unknown_subagent_raises(self) -> None:
        """Delegation to a nonexistent subagent raises ToolError."""
        provider = MockProvider([])
        agent = Agent(name="main", model="test-model", provider=provider)

        with pytest.raises(ToolError, match="Unknown subagent: ghost"):
            await agent.delegate("ghost", "Do something")


class TestAgentSystemMessage:
    """Tests for system message construction from body and skills."""

    @pytest.mark.asyncio
    async def test_system_message_from_body(self) -> None:
        """Body text becomes the system message."""
        provider = MockProvider([_text_result("ok")])
        agent = Agent(
            name="body-agent",
            model="test-model",
            body="You are a helpful assistant.",
            provider=provider,
        )

        await agent.run("Hi")

        messages = provider.call_args[0]["messages"]
        assert messages[0].role == "system"
        assert messages[0].content == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_system_message_description_not_included(self) -> None:
        """Description is metadata and is not added as system message content."""
        provider = MockProvider([_text_result("ok")])
        agent = Agent(
            name="sp-agent",
            model="test-model",
            description="Always respond in JSON.",
            provider=provider,
        )

        await agent.run("Hi")

        messages = provider.call_args[0]["messages"]
        assert messages[0].role == "user"
        assert messages[0].content == "Hi"

    @pytest.mark.asyncio
    async def test_system_message_uses_body_not_description(self) -> None:
        """Body is used for system message content; description is ignored."""
        provider = MockProvider([_text_result("ok")])
        agent = Agent(
            name="combined",
            model="test-model",
            description="You are a wizard.",
            body="Speak in riddles.",
            provider=provider,
        )

        await agent.run("Hi")

        messages = provider.call_args[0]["messages"]
        assert messages[0].role == "system"
        assert messages[0].content == "Speak in riddles."

    @pytest.mark.asyncio
    async def test_no_system_message_when_empty(self) -> None:
        """No system message is added when both description and body are empty."""
        provider = MockProvider([_text_result("ok")])
        agent = Agent(name="bare", model="test-model", provider=provider)

        await agent.run("Hi")

        messages = provider.call_args[0]["messages"]
        assert messages[0].role == "user"
        assert messages[0].content == "Hi"


class TestAgentToolRegistration:
    """Tests for tool registration during Agent construction."""

    def test_tools_registered_from_functions(self) -> None:
        """@tool-decorated functions are registered in the agent's tool registry."""
        provider = MockProvider([])
        agent = Agent(
            name="tool-agent",
            model="test-model",
            tools=[add, greet],
            provider=provider,
        )

        schemas = agent.tool_registry.get_schemas()
        schema_names = {s.name for s in schemas}
        assert "add" in schema_names
        assert "greet" in schema_names

    def test_no_tools_empty_registry(self) -> None:
        """Agent with no tools has an empty tool registry."""
        provider = MockProvider([])
        agent = Agent(name="no-tools", model="test-model", provider=provider)

        assert agent.tool_registry.get_schemas() == []


class TestAgentFromConfig:
    """Tests for Agent.from_config — loading from Markdown."""

    def test_from_config(self, tmp_path: Path) -> None:
        """Load an agent from a Markdown config file."""
        config_md = textwrap.dedent("""\
            ---
            name: test-agent
            model: gpt-4o
            description: You are helpful.
            max_turns: 5
            ---

            Be concise.
        """)
        config_file = tmp_path / "AGENTS.md"
        config_file.write_text(config_md)

        agent = Agent.from_config(config_file)

        assert agent.name == "test-agent"
        assert agent.model == "gpt-4o"
        assert agent.description == "You are helpful."
        assert agent.max_turns == 5
        assert agent._body == "Be concise."

    def test_from_config_with_subagents(self, tmp_path: Path) -> None:
        """Load an agent with subagents from config."""
        config_md = textwrap.dedent("""\
            ---
            name: parent
            model: gpt-4o
            subagents:
              - name: child
                model: gpt-4o-mini
                description: I am a child agent.
            ---
        """)
        config_file = tmp_path / "AGENTS.md"
        config_file.write_text(config_md)

        agent = Agent.from_config(config_file)

        assert agent.name == "parent"
        assert "child" in agent.subagents
        child = agent.subagents["child"]
        assert child.name == "child"
        assert child.model == "gpt-4o-mini"
        assert child.description == "I am a child agent."

    def test_from_config_with_description_file_path(self, tmp_path: Path) -> None:
        """Description preserves literal text (including .md path-like values)."""
        description_path = "description.md"

        config_md = textwrap.dedent("""\
            ---
            name: md-agent
            model: gpt-4o
            description: description.md
            ---
        """)
        config_file = tmp_path / "AGENTS.md"
        config_file.write_text(config_md)

        agent = Agent.from_config(config_file)

        assert agent.description == description_path


class TestAgentInit:
    """Tests for Agent constructor edge cases."""

    def test_default_subagents_empty(self) -> None:
        """Subagents default to an empty dict."""
        provider = MockProvider([])
        agent = Agent(name="test", model="m", provider=provider)
        assert agent.subagents == {}

    def test_default_max_turns(self) -> None:
        """Default max_turns is 10."""
        provider = MockProvider([])
        agent = Agent(name="test", model="m", provider=provider)
        assert agent.max_turns == 10

    def test_memory_stored_as_attribute(self) -> None:
        """Memory is stored but not used in the execution loop yet."""
        provider = MockProvider([])
        agent = Agent(name="test", model="m", provider=provider, memory=None)
        assert agent.memory is None


class TestAgentModelParams:
    """Tests for model_params forwarding to LiteLLMProvider."""

    def test_model_params_forwarded_to_provider(self) -> None:
        """model_params kwargs are stored in the provider's config."""
        from sage.providers.litellm_provider import LiteLLMProvider

        agent = Agent(
            name="test",
            model="gpt-4o",
            model_params={"temperature": 0.3, "max_tokens": 1024, "seed": 42},
        )

        assert isinstance(agent.provider, LiteLLMProvider)
        assert agent.provider.config["temperature"] == 0.3
        assert agent.provider.config["max_tokens"] == 1024
        assert agent.provider.config["seed"] == 42

    def test_empty_model_params_no_extra_config(self) -> None:
        """None or empty model_params leaves provider config empty."""
        from sage.providers.litellm_provider import LiteLLMProvider

        agent = Agent(name="test", model="gpt-4o", model_params=None)

        assert isinstance(agent.provider, LiteLLMProvider)
        assert agent.provider.config == {}

    def test_model_params_not_forwarded_when_provider_supplied(self) -> None:
        """When a custom provider is passed, model_params are ignored."""
        provider = MockProvider([])
        agent = Agent(
            name="test",
            model="gpt-4o",
            provider=provider,
            model_params={"temperature": 0.9},
        )
        # The explicitly supplied provider is used unchanged.
        assert agent.provider is provider

    def test_from_config_forwards_model_params(self, tmp_path: Path) -> None:
        """model_params in frontmatter are wired through to the provider."""
        import textwrap

        from sage.providers.litellm_provider import LiteLLMProvider

        config_md = textwrap.dedent("""\
            ---
            name: test-agent
            model: gpt-4o
            model_params:
              temperature: 0.7
              max_tokens: 512
            ---
        """)
        config_file = tmp_path / "AGENTS.md"
        config_file.write_text(config_md)

        agent = Agent.from_config(config_file)

        assert isinstance(agent.provider, LiteLLMProvider)
        assert agent.provider.config["temperature"] == 0.7
        assert agent.provider.config["max_tokens"] == 512

    def test_from_config_no_model_params_empty_provider_config(self, tmp_path: Path) -> None:
        """Agent loaded from config without model_params has empty provider config."""
        import textwrap

        from sage.providers.litellm_provider import LiteLLMProvider

        config_md = textwrap.dedent("""\
            ---
            name: test-agent
            model: gpt-4o
            ---
        """)
        config_file = tmp_path / "AGENTS.md"
        config_file.write_text(config_md)

        agent = Agent.from_config(config_file)

        assert isinstance(agent.provider, LiteLLMProvider)
        assert agent.provider.config == {}


class TestAgentSkills:
    """Tests for skills loading and injection into the system message."""

    def test_no_skills_by_default(self) -> None:
        """Agent with no skills has an empty skills list."""
        provider = MockProvider([])
        agent = Agent(name="test", model="m", provider=provider)
        assert agent.skills == []

    @pytest.mark.asyncio
    async def test_skill_injected_into_system_message(self) -> None:
        """A skill's content appears in the system message sent to the provider."""
        from sage.skills.loader import Skill

        skill = Skill(
            name="my-skill",
            description="Does something useful",
            content="Always start with step 1.",
        )
        provider = MockProvider([_text_result("ok")])
        agent = Agent(
            name="test",
            model="m",
            body="Base body.",
            skills=[skill],
            provider=provider,
        )

        await agent.run("hi")

        messages = provider.call_args[0]["messages"]
        system_msg = next(m for m in messages if m.role == "system")
        assert "## Skill: my-skill" in system_msg.content
        assert "_Does something useful_" in system_msg.content
        assert "Always start with step 1." in system_msg.content

    @pytest.mark.asyncio
    async def test_multiple_skills_all_injected(self) -> None:
        """All skills are appended to the system message."""
        from sage.skills.loader import Skill

        skills = [
            Skill(name="skill-a", content="Content A."),
            Skill(name="skill-b", content="Content B."),
        ]
        provider = MockProvider([_text_result("ok")])
        agent = Agent(name="test", model="m", skills=skills, provider=provider)

        await agent.run("hi")

        messages = provider.call_args[0]["messages"]
        system_msg = next(m for m in messages if m.role == "system")
        assert "## Skill: skill-a" in system_msg.content
        assert "Content A." in system_msg.content
        assert "## Skill: skill-b" in system_msg.content
        assert "Content B." in system_msg.content

    @pytest.mark.asyncio
    async def test_skills_appended_after_persona(self) -> None:
        """Skills appear after body content in the system message."""
        from sage.skills.loader import Skill

        skill = Skill(name="s", content="Skill content.")
        provider = MockProvider([_text_result("ok")])
        agent = Agent(
            name="test",
            model="m",
            body="My body.",
            skills=[skill],
            provider=provider,
        )

        await agent.run("hi")

        messages = provider.call_args[0]["messages"]
        system_msg = next(m for m in messages if m.role == "system")
        body_pos = system_msg.content.index("My body.")
        skill_pos = system_msg.content.index("## Skill: s")
        assert body_pos < skill_pos

    def test_from_config_auto_discovers_skills_dir(self, tmp_path: Path) -> None:
        """Skills in a 'skills/' directory next to the config are auto-discovered."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "my-skill.md").write_text(
            "---\nname: my-skill\ndescription: Test skill\n---\n\nSkill body.",
            encoding="utf-8",
        )

        config_file = tmp_path / "AGENTS.md"
        config_file.write_text(
            "---\nname: test\nmodel: gpt-4o\n---\n",
            encoding="utf-8",
        )

        agent = Agent.from_config(config_file)

        assert len(agent.skills) == 1
        assert agent.skills[0].name == "my-skill"
        assert agent.skills[0].description == "Test skill"
        assert "Skill body." in agent.skills[0].content

    def test_from_config_no_skills_dir_yields_empty(self, tmp_path: Path) -> None:
        """No auto-discovered skills when 'skills/' directory does not exist."""
        config_file = tmp_path / "AGENTS.md"
        config_file.write_text("---\nname: test\nmodel: gpt-4o\n---\n", encoding="utf-8")

        agent = Agent.from_config(config_file)

        assert agent.skills == []

    def test_from_config_skills_dir_override(self, tmp_path: Path) -> None:
        """skills_dir in frontmatter overrides auto-discovery."""
        custom_dir = tmp_path / "custom_skills"
        custom_dir.mkdir()
        (custom_dir / "override-skill.md").write_text(
            "---\nname: override-skill\n---\n\nOverride content.",
            encoding="utf-8",
        )
        # Also create a default 'skills/' dir — should be ignored.
        default_dir = tmp_path / "skills"
        default_dir.mkdir()
        (default_dir / "ignored.md").write_text("name: ignored\n\nIgnored.", encoding="utf-8")

        config_file = tmp_path / "AGENTS.md"
        config_file.write_text(
            "---\nname: test\nmodel: gpt-4o\nskills_dir: custom_skills\n---\n",
            encoding="utf-8",
        )

        agent = Agent.from_config(config_file)

        assert len(agent.skills) == 1
        assert agent.skills[0].name == "override-skill"

    def test_from_config_directory_per_skill(self, tmp_path: Path) -> None:
        """Skills stored as subdirectories (dir/skill.md) are loaded correctly."""
        skills_dir = tmp_path / "skills"
        skill_subdir = skills_dir / "code-review"
        skill_subdir.mkdir(parents=True)
        (skill_subdir / "skill.md").write_text(
            "---\nname: code-review\ndescription: Review code\n---\n\nReview steps.",
            encoding="utf-8",
        )

        config_file = tmp_path / "AGENTS.md"
        config_file.write_text("---\nname: test\nmodel: gpt-4o\n---\n", encoding="utf-8")

        agent = Agent.from_config(config_file)

        assert len(agent.skills) == 1
        assert agent.skills[0].name == "code-review"
        assert agent.skills[0].description == "Review code"
        assert "Review steps." in agent.skills[0].content

    def test_from_config_dir_name_used_when_no_frontmatter_name(self, tmp_path: Path) -> None:
        """When skill.md has no frontmatter name, the directory name is used."""
        skills_dir = tmp_path / "skills"
        skill_subdir = skills_dir / "my-technique"
        skill_subdir.mkdir(parents=True)
        (skill_subdir / "skill.md").write_text("Just content, no frontmatter.", encoding="utf-8")

        config_file = tmp_path / "AGENTS.md"
        config_file.write_text("---\nname: test\nmodel: gpt-4o\n---\n", encoding="utf-8")

        agent = Agent.from_config(config_file)

        assert agent.skills[0].name == "my-technique"


class TestAgentLogging:
    """Tests for logging in Agent.run."""

    @pytest.mark.asyncio
    async def test_run_logs_start_and_end(self, caplog: pytest.LogCaptureFixture) -> None:
        """Agent.run should log INFO at start and end with the agent name."""
        provider = MockProvider([_text_result("Hello")])
        agent = Agent(name="test-agent", model="gpt-4o", provider=provider)

        with caplog.at_level(logging.INFO, logger="sage.agent"):
            await agent.run("test input")

        messages = [r.message for r in caplog.records]
        assert any("test-agent" in m for m in messages), (
            f"Expected agent name in logs, got: {messages}"
        )

    @pytest.mark.asyncio
    async def test_run_logs_tool_dispatch(self, caplog: pytest.LogCaptureFixture) -> None:
        """Agent.run should log DEBUG when tool calls are dispatched."""
        tool_calls = [ToolCall(id="1", name="add", arguments={"a": 1, "b": 2})]
        provider = MockProvider(
            [
                _tool_call_result(tool_calls),
                _text_result("The answer is 3"),
            ]
        )
        agent = Agent(name="calc", model="gpt-4o", provider=provider, tools=[add])

        with caplog.at_level(logging.DEBUG, logger="sage.agent"):
            await agent.run("What is 1 + 2?")

        all_messages = " ".join(r.message for r in caplog.records)
        assert "add" in all_messages, f"Expected tool name 'add' in logs, got: {all_messages}"


# ── MCP wiring tests ──────────────────────────────────────────────────────────


class TestAgentMCPWiring:
    """Tests for MCP server integration in the Agent."""

    @pytest.mark.asyncio
    async def test_mcp_tools_registered_on_first_run(self) -> None:
        """MCP tools are discovered and registered before the first LLM turn."""
        from unittest.mock import AsyncMock

        from sage.models import ToolSchema

        mcp_schema = ToolSchema(
            name="mcp_hello",
            description="Say hello via MCP",
            parameters={},
        )
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.discover_tools = AsyncMock(return_value=[mcp_schema])
        mock_client.call_tool = AsyncMock(return_value="hello from MCP")

        provider = MockProvider([_text_result("done")])
        agent = Agent(
            name="mcp-agent",
            model="test-model",
            provider=provider,
            mcp_clients=[mock_client],
        )

        await agent.run("test")

        mock_client.connect.assert_awaited_once()
        mock_client.discover_tools.assert_awaited_once()
        # Schema should now be visible in the registry.
        names = {s.name for s in agent.tool_registry.get_schemas()}
        assert "mcp_hello" in names

    @pytest.mark.asyncio
    async def test_mcp_tools_only_connected_once(self) -> None:
        """MCP servers are connected only on the first run call (idempotent)."""
        from unittest.mock import AsyncMock

        from sage.models import ToolSchema

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.discover_tools = AsyncMock(
            return_value=[
                ToolSchema(name="t", description="", parameters={}),
            ]
        )

        provider = MockProvider([_text_result("ok"), _text_result("ok")])
        agent = Agent(
            name="mcp-agent",
            model="test-model",
            provider=provider,
            mcp_clients=[mock_client],
        )

        await agent.run("first")
        await agent.run("second")

        # connect() called exactly once across both run() calls.
        assert mock_client.connect.await_count == 1

    @pytest.mark.asyncio
    async def test_mcp_tool_called_when_model_requests_it(self) -> None:
        """When the model emits a tool call for an MCP tool, it routes to the client."""
        from unittest.mock import AsyncMock

        from sage.models import ToolCall, ToolSchema

        mcp_schema = ToolSchema(
            name="list_files",
            description="List files",
            parameters={},
        )
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.discover_tools = AsyncMock(return_value=[mcp_schema])
        mock_client.call_tool = AsyncMock(return_value="a.txt\nb.txt")

        tool_call = ToolCall(id="tc_mcp", name="list_files", arguments={"path": "/"})
        provider = MockProvider(
            [
                _tool_call_result([tool_call]),
                _text_result("Found: a.txt, b.txt"),
            ]
        )
        agent = Agent(
            name="mcp-agent",
            model="test-model",
            provider=provider,
            mcp_clients=[mock_client],
        )

        result = await agent.run("list files")

        mock_client.call_tool.assert_awaited_once_with("list_files", {"path": "/"})
        assert result == "Found: a.txt, b.txt"

    @pytest.mark.asyncio
    async def test_mcp_connection_failure_is_logged_not_raised(self) -> None:
        """A failed MCP connection logs an error but does not abort run()."""
        from unittest.mock import AsyncMock

        from sage.exceptions import SageError

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=SageError("server not found"))

        provider = MockProvider([_text_result("ok")])
        agent = Agent(
            name="mcp-agent",
            model="test-model",
            provider=provider,
            mcp_clients=[mock_client],
        )

        # Should not raise; agent still runs with no MCP tools.
        result = await agent.run("hi")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_from_config_creates_mcp_clients(self, tmp_path: Path) -> None:
        """mcp_servers in frontmatter results in MCPClient instances on the agent."""
        config_md = textwrap.dedent("""\
            ---
            name: mcp-test
            model: gpt-4o
            mcp_servers:
              echo-server:
                transport: stdio
                command: echo
                args: [hello]
            ---
        """)
        (tmp_path / "AGENTS.md").write_text(config_md)
        agent = Agent.from_config(tmp_path / "AGENTS.md")

        assert len(agent.mcp_clients) == 1
        assert agent.mcp_clients[0]._command == "echo"
        assert agent.mcp_clients[0]._args == ["hello"]


# ── Memory wiring tests ───────────────────────────────────────────────────────


class TestAgentMemoryWiring:
    """Tests for memory recall and store integration in Agent.run()."""

    @pytest.mark.asyncio
    async def test_memory_recalled_before_first_turn(self) -> None:
        """Recalled memory is injected as a system message before the user input."""
        from unittest.mock import AsyncMock

        from sage.memory.base import MemoryEntry

        mock_memory = AsyncMock()
        mock_memory.recall = AsyncMock(
            return_value=[
                MemoryEntry(id="1", content="Paris is the capital of France."),
            ]
        )
        mock_memory.store = AsyncMock()

        provider = MockProvider([_text_result("Paris")])
        agent = Agent(
            name="mem-agent",
            model="test-model",
            provider=provider,
            memory=mock_memory,
        )

        await agent.run("What is the capital of France?")

        mock_memory.recall.assert_awaited_once_with("What is the capital of France?")
        # The memory context message should appear in the messages sent to the provider.
        messages = provider.call_args[0]["messages"]
        system_messages = [m for m in messages if m.role == "system"]
        combined = " ".join(m.content or "" for m in system_messages)
        assert "Paris is the capital of France." in combined

    @pytest.mark.asyncio
    async def test_memory_stored_after_successful_run(self) -> None:
        """The exchange is stored in memory after run() completes."""
        from unittest.mock import AsyncMock

        mock_memory = AsyncMock()
        mock_memory.recall = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock()

        provider = MockProvider([_text_result("42")])
        agent = Agent(
            name="mem-agent",
            model="test-model",
            provider=provider,
            memory=mock_memory,
        )

        await agent.run("What is the meaning of life?")

        mock_memory.store.assert_awaited_once()
        stored_content = mock_memory.store.call_args[0][0]
        assert "What is the meaning of life?" in stored_content
        assert "42" in stored_content

    @pytest.mark.asyncio
    async def test_memory_stored_after_max_turns(self) -> None:
        """The final assistant content is persisted even when max_turns is hit."""
        from unittest.mock import AsyncMock

        mock_memory = AsyncMock()
        mock_memory.recall = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock()

        from sage.models import ToolCall

        tool_calls = [ToolCall(id="tc", name="add", arguments={"a": 1, "b": 1})]
        provider = MockProvider(
            [
                _tool_call_result(tool_calls, content="thinking..."),
                _tool_call_result(tool_calls, content="still thinking..."),
            ]
        )
        from sage.tools.decorator import tool as _tool

        @_tool
        def add(a: int, b: int) -> int:
            """Add."""
            return a + b

        agent = Agent(
            name="mem-agent",
            model="test-model",
            provider=provider,
            memory=mock_memory,
            tools=[add],
            max_turns=2,
        )

        from sage.exceptions import MaxTurnsExceeded

        with pytest.raises(MaxTurnsExceeded):
            await agent.run("loop")

        # store() should still have been called.
        mock_memory.store.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_memory_recall_failure_does_not_abort_run(self) -> None:
        """A failing memory recall is logged and run() continues normally."""
        from unittest.mock import AsyncMock

        mock_memory = AsyncMock()
        mock_memory.recall = AsyncMock(side_effect=RuntimeError("db gone"))
        mock_memory.store = AsyncMock()

        provider = MockProvider([_text_result("fine")])
        agent = Agent(
            name="mem-agent",
            model="test-model",
            provider=provider,
            memory=mock_memory,
        )

        result = await agent.run("hi")
        assert result == "fine"

    @pytest.mark.asyncio
    async def test_no_memory_context_message_when_recall_empty(self) -> None:
        """When recall returns nothing, no extra system message is injected."""
        from unittest.mock import AsyncMock

        mock_memory = AsyncMock()
        mock_memory.recall = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock()

        provider = MockProvider([_text_result("ok")])
        agent = Agent(
            name="mem-agent",
            model="test-model",
            provider=provider,
            memory=mock_memory,
        )

        await agent.run("hi")

        messages = provider.call_args[0]["messages"]
        # Only the user message — no system message at all.
        assert len(messages) == 1
        assert messages[0].role == "user"

    def test_from_config_creates_sqlite_memory(self, tmp_path: Path) -> None:
        """memory.backend=sqlite in frontmatter results in a SQLiteMemory on the agent."""
        from sage.memory.sqlite_backend import SQLiteMemory

        config_md = textwrap.dedent("""\
            ---
            name: mem-test
            model: gpt-4o
            memory:
              backend: sqlite
              path: ./test_memory.db
              embedding: text-embedding-ada-002
            ---
        """)
        (tmp_path / "AGENTS.md").write_text(config_md)
        agent = Agent.from_config(tmp_path / "AGENTS.md")

        assert isinstance(agent.memory, SQLiteMemory)
        assert agent.memory._path == "./test_memory.db"
        # Verify embedding uses the memory config's embedding model,
        # NOT the chat model.
        assert agent.memory._embedding._model == "text-embedding-ada-002"

    def test_from_config_no_memory_when_not_configured(self, tmp_path: Path) -> None:
        """Agent has no memory when frontmatter has no 'memory:' key."""
        config_md = textwrap.dedent("""\
            ---
            name: no-mem
            model: gpt-4o
            ---
        """)
        (tmp_path / "AGENTS.md").write_text(config_md)
        agent = Agent.from_config(tmp_path / "AGENTS.md")

        assert agent.memory is None


class TestAgentMemoryInitialize:
    """Tests for automatic memory initialization and close lifecycle."""

    @pytest.mark.asyncio
    async def test_memory_initialized_before_first_run(self) -> None:
        """_ensure_memory_initialized is called once before recall on first run."""
        from unittest.mock import AsyncMock

        from sage.memory.base import MemoryEntry

        mock_memory = AsyncMock()
        mock_memory.initialize = AsyncMock()
        mock_memory.recall = AsyncMock(
            return_value=[
                MemoryEntry(id="1", content="hello"),
            ]
        )
        mock_memory.store = AsyncMock()

        provider = MockProvider([_text_result("hi")])
        agent = Agent(
            name="init-agent",
            model="test-model",
            provider=provider,
            memory=mock_memory,
        )

        await agent.run("hello")

        mock_memory.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_memory_initialized_only_once_across_runs(self) -> None:
        """initialize() is called exactly once even over multiple run() calls."""
        from unittest.mock import AsyncMock

        mock_memory = AsyncMock()
        mock_memory.initialize = AsyncMock()
        mock_memory.recall = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock()

        provider = MockProvider([_text_result("a"), _text_result("b")])
        agent = Agent(
            name="init-once",
            model="test-model",
            provider=provider,
            memory=mock_memory,
        )

        await agent.run("first")
        await agent.run("second")

        assert mock_memory.initialize.await_count == 1

    @pytest.mark.asyncio
    async def test_agent_close_calls_memory_close(self) -> None:
        """agent.close() delegates to memory.close() and resets initialized flag."""
        from unittest.mock import AsyncMock

        mock_memory = AsyncMock()
        mock_memory.initialize = AsyncMock()
        mock_memory.close = AsyncMock()
        mock_memory.recall = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock()

        provider = MockProvider([_text_result("ok")])
        agent = Agent(
            name="close-agent",
            model="test-model",
            provider=provider,
            memory=mock_memory,
        )

        await agent.run("test")
        await agent.close()

        mock_memory.close.assert_awaited_once()
        assert agent._memory_initialized is False

    @pytest.mark.asyncio
    async def test_agent_close_reinitializes_on_next_run(self) -> None:
        """After close(), a subsequent run() re-initializes memory."""
        from unittest.mock import AsyncMock

        mock_memory = AsyncMock()
        mock_memory.initialize = AsyncMock()
        mock_memory.close = AsyncMock()
        mock_memory.recall = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock()

        provider = MockProvider([_text_result("first"), _text_result("second")])
        agent = Agent(
            name="reopen-agent",
            model="test-model",
            provider=provider,
            memory=mock_memory,
        )

        await agent.run("run 1")
        await agent.close()
        await agent.run("run 2")

        assert mock_memory.initialize.await_count == 2

    @pytest.mark.asyncio
    async def test_close_without_memory_is_safe(self) -> None:
        """agent.close() is a no-op when no memory backend is configured."""
        provider = MockProvider([])
        agent = Agent(name="no-mem", model="test-model", provider=provider)
        # Should not raise
        await agent.close()


class TestAgentDelegationTool:
    """Tests for auto-registered delegation tool when subagents are present."""

    def test_delegate_tool_registered_when_subagents_present(self) -> None:
        """Agent with subagents auto-registers a 'delegate' tool."""
        sub_provider = MockProvider([])
        subagent = Agent(name="helper", model="test-model", provider=sub_provider)
        main_provider = MockProvider([])
        agent = Agent(
            name="main",
            model="test-model",
            provider=main_provider,
            subagents={"helper": subagent},
        )

        schema_names = {s.name for s in agent.tool_registry.get_schemas()}
        assert "delegate" in schema_names

    def test_delegate_tool_not_registered_without_subagents(self) -> None:
        """Agent without subagents has no 'delegate' tool."""
        provider = MockProvider([])
        agent = Agent(name="solo", model="test-model", provider=provider)

        schema_names = {s.name for s in agent.tool_registry.get_schemas()}
        assert "delegate" not in schema_names

    def test_delegate_tool_schema_lists_subagent_names(self) -> None:
        """The delegate tool schema enumerates available subagent names."""
        sub_a = Agent(name="alpha", model="m", provider=MockProvider([]))
        sub_b = Agent(name="beta", model="m", description="Beta helper", provider=MockProvider([]))
        agent = Agent(
            name="orch",
            model="m",
            provider=MockProvider([]),
            subagents={"alpha": sub_a, "beta": sub_b},
        )

        schemas = {s.name: s for s in agent.tool_registry.get_schemas()}
        delegate_schema = schemas["delegate"]
        agent_name_prop = delegate_schema.parameters["properties"]["agent_name"]
        assert set(agent_name_prop["enum"]) == {"alpha", "beta"}
        assert "beta: Beta helper" in delegate_schema.description

    @pytest.mark.asyncio
    async def test_delegate_tool_invoked_via_run_loop(self) -> None:
        """When the LLM emits a delegate tool call, the subagent is actually invoked."""
        sub_provider = MockProvider([_text_result("Subagent did the work.")])
        subagent = Agent(name="worker", model="test-model", provider=sub_provider)

        tool_calls = [
            ToolCall(
                id="tc_del",
                name="delegate",
                arguments={"agent_name": "worker", "task": "Do the thing"},
            )
        ]
        main_provider = MockProvider(
            [
                _tool_call_result(tool_calls),
                _text_result("Worker says: Subagent did the work."),
            ]
        )
        agent = Agent(
            name="orchestrator",
            model="test-model",
            provider=main_provider,
            subagents={"worker": subagent},
        )

        result = await agent.run("Delegate this to worker")

        assert result == "Worker says: Subagent did the work."
        assert sub_provider.call_count == 1
        assert main_provider.call_count == 2

        # Verify the subagent result was fed back as a tool result.
        second_call_msgs = main_provider.call_args[1]["messages"]
        tool_msgs = [m for m in second_call_msgs if m.role == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].content == "Subagent did the work."
        assert tool_msgs[0].tool_call_id == "tc_del"

    @pytest.mark.asyncio
    async def test_delegate_tool_unknown_subagent_returns_error(self) -> None:
        """Delegating to an unknown subagent returns an error message (not crash)."""
        sub_provider = MockProvider([])
        subagent = Agent(name="worker", model="test-model", provider=sub_provider)

        tool_calls = [
            ToolCall(
                id="tc_bad",
                name="delegate",
                arguments={"agent_name": "ghost", "task": "Do something"},
            )
        ]
        main_provider = MockProvider(
            [
                _tool_call_result(tool_calls),
                _text_result("Could not find that agent."),
            ]
        )
        agent = Agent(
            name="orchestrator",
            model="test-model",
            provider=main_provider,
            subagents={"worker": subagent},
        )

        result = await agent.run("Delegate to ghost")

        assert result == "Could not find that agent."
        # The error should have been passed back as a tool result.
        second_call_msgs = main_provider.call_args[1]["messages"]
        tool_msgs = [m for m in second_call_msgs if m.role == "tool"]
        assert len(tool_msgs) == 1
        assert "Unknown subagent: ghost" in tool_msgs[0].content

    @pytest.mark.asyncio
    async def test_delegate_tool_coexists_with_other_tools(self) -> None:
        """Delegate tool and regular tools are both available."""
        sub_provider = MockProvider([_text_result("Sub result")])
        subagent = Agent(name="helper", model="m", provider=sub_provider)

        provider = MockProvider([])
        agent = Agent(
            name="orch",
            model="m",
            provider=provider,
            tools=[add],
            subagents={"helper": subagent},
        )

        schema_names = {s.name for s in agent.tool_registry.get_schemas()}
        assert "add" in schema_names
        assert "delegate" in schema_names


# ── Conversation History Tests ─────────────────────────────────────────────


class TestAgentConversationHistory:
    """Tests for multi-turn conversation history accumulation."""

    @pytest.mark.asyncio
    async def test_history_accumulated_across_runs(self) -> None:
        """Successive run() calls see prior conversation turns."""
        provider = MockProvider(
            [
                _text_result("Paris."),
                _text_result("About 2.1 million."),
            ]
        )
        agent = Agent(name="test", model="m", provider=provider)

        await agent.run("What is the capital of France?")
        await agent.run("What is its population?")

        # The second call should contain the first user+assistant pair.
        second_call_msgs = provider.call_args[1]["messages"]
        roles = [m.role for m in second_call_msgs]
        # Expect: user(turn1), assistant(turn1), user(turn2)
        assert "user" in roles
        assert "assistant" in roles
        # The first user message should be in the second call.
        contents = [m.content for m in second_call_msgs if m.role == "user"]
        assert "What is the capital of France?" in contents
        assert "What is its population?" in contents

    @pytest.mark.asyncio
    async def test_history_accumulated_across_streams(self) -> None:
        """Successive stream() calls see prior conversation turns."""
        provider = MockProvider(
            [
                _text_result("Paris."),
                _text_result("About 2.1 million."),
            ]
        )
        agent = Agent(name="test", model="m", provider=provider)

        [c async for c in agent.stream("Capital of France?")]
        [c async for c in agent.stream("Population?")]

        second_call_msgs = provider.call_args[1]["messages"]
        user_msgs = [m.content for m in second_call_msgs if m.role == "user"]
        assert "Capital of France?" in user_msgs
        assert "Population?" in user_msgs

    @pytest.mark.asyncio
    async def test_history_across_run_then_stream(self) -> None:
        """run() followed by stream() should carry history forward."""
        provider = MockProvider(
            [
                _text_result("Paris."),
                _text_result("Berlin."),
            ]
        )
        agent = Agent(name="test", model="m", provider=provider)

        await agent.run("Capital of France?")
        [c async for c in agent.stream("Capital of Germany?")]

        second_call_msgs = provider.call_args[1]["messages"]
        user_msgs = [m.content for m in second_call_msgs if m.role == "user"]
        assert "Capital of France?" in user_msgs
        assert "Capital of Germany?" in user_msgs

    @pytest.mark.asyncio
    async def test_clear_history_resets(self) -> None:
        """clear_history() removes all prior turns."""
        provider = MockProvider(
            [
                _text_result("First."),
                _text_result("Second."),
            ]
        )
        agent = Agent(name="test", model="m", provider=provider)

        await agent.run("Turn 1")
        agent.clear_history()
        await agent.run("Turn 2")

        # The second call should NOT contain turn 1.
        second_call_msgs = provider.call_args[1]["messages"]
        user_msgs = [m.content for m in second_call_msgs if m.role == "user"]
        assert "Turn 1" not in user_msgs
        assert "Turn 2" in user_msgs

    @pytest.mark.asyncio
    async def test_history_contains_correct_assistant_content(self) -> None:
        """The assistant turn saved to history matches what run() returned."""
        provider = MockProvider(
            [
                _text_result("Answer 1"),
                _text_result("Answer 2"),
            ]
        )
        agent = Agent(name="test", model="m", provider=provider)

        result1 = await agent.run("Q1")
        assert result1 == "Answer 1"

        await agent.run("Q2")

        # Inspect history directly.
        history = agent._conversation_history
        assert len(history) == 4  # 2 user + 2 assistant
        assert history[0] == Message(role="user", content="Q1")
        assert history[1] == Message(role="assistant", content="Answer 1")
        assert history[2] == Message(role="user", content="Q2")
        assert history[3] == Message(role="assistant", content="Answer 2")

    @pytest.mark.asyncio
    async def test_history_with_tool_calls(self) -> None:
        """History records final assistant content even after tool loops."""
        tool_calls = [ToolCall(id="tc_1", name="add", arguments={"a": 1, "b": 2})]
        provider = MockProvider(
            [
                _tool_call_result(tool_calls),
                _text_result("Result is 3."),
                _text_result("I remember that."),
            ]
        )
        agent = Agent(name="test", model="m", provider=provider, tools=[add])

        await agent.run("Add 1 and 2")
        await agent.run("What did you get?")

        history = agent._conversation_history
        assert len(history) == 4
        assert history[1].content == "Result is 3."
        assert history[3].content == "I remember that."


class TestAgentCompaction:
    """Tests for conversation history compaction."""

    @pytest.mark.asyncio
    async def test_compaction_triggered_when_threshold_exceeded(self) -> None:
        """History is compacted when it exceeds the threshold."""
        # 6 exchanges = 12 messages. Threshold=10, keep_recent=10.
        # After run 5 (index 5): history=12, exceeds 10 → compaction.
        # compact_messages summarises 2 oldest, keeps 10 recent.
        # Provider calls: 6 runs + 1 summarisation = 7 total.
        responses = [_text_result(f"Response {i}") for i in range(6)]
        responses.append(_text_result("Summary of earlier conversation."))  # for compact
        provider = MockProvider(responses)
        agent = Agent(name="test", model="m", provider=provider)
        agent._compaction_threshold = 10

        for i in range(6):
            await agent.run(f"Question {i}")

        # Without compaction history would be 12; compaction replaces
        # the 2 oldest with a single system summary → 11 items.
        assert len(agent._conversation_history) == 11

    @pytest.mark.asyncio
    async def test_no_compaction_below_threshold(self) -> None:
        """History is NOT compacted when below threshold (default=50)."""
        provider = MockProvider(
            [
                _text_result("R1"),
                _text_result("R2"),
            ]
        )
        agent = Agent(name="test", model="m", provider=provider)

        await agent.run("Q1")
        await agent.run("Q2")

        # Default threshold is 50 — with 4 messages, no compaction.
        assert len(agent._conversation_history) == 4

    @pytest.mark.asyncio
    async def test_clear_history_after_compaction(self) -> None:
        """clear_history() works after compaction has occurred."""
        responses = [_text_result(f"R{i}") for i in range(5)]
        provider = MockProvider(responses)
        agent = Agent(name="test", model="m", provider=provider)
        agent._compaction_threshold = 2  # Aggressively compact

        for i in range(3):
            await agent.run(f"Q{i}")

        agent.clear_history()
        assert len(agent._conversation_history) == 0


class TestStreamChunkUsage:
    @pytest.mark.asyncio
    async def test_streamchunk_usage_default_none(self) -> None:
        chunk = StreamChunk(delta="hello")

        assert chunk.usage is None

    @pytest.mark.asyncio
    async def test_streamchunk_usage_can_be_set(self) -> None:
        chunk = StreamChunk(
            delta="hello",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

        assert chunk.usage is not None
        assert chunk.usage.prompt_tokens == 10
        assert chunk.usage.total_tokens == 15

    @pytest.mark.asyncio
    async def test_streamchunk_usage_with_zero_tokens(self) -> None:
        chunk = StreamChunk(
            delta="",
            usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

        assert chunk.usage is not None
        assert chunk.usage.total_tokens == 0


class TestAgentTokenTracking:
    @pytest.mark.asyncio
    async def test_initial_token_state(self) -> None:
        provider = MockProvider([_text_result("ok")])
        agent = Agent(name="t", model="m", provider=provider)

        assert agent._token_usage == 0
        assert agent._context_window_limit is None
        assert not agent._context_window_detected
        assert agent._turns_since_compaction == 0
        assert agent._token_compaction_threshold == 0.8

    @pytest.mark.asyncio
    async def test_get_usage_stats_no_limit(self) -> None:
        provider = MockProvider([_text_result("ok")])
        agent = Agent(name="t", model="m", provider=provider)

        stats = agent.get_usage_stats()

        assert "token_usage" in stats
        assert isinstance(stats["token_usage"], int)
        assert stats["token_usage"] == 0
        assert stats["context_window_limit"] is None
        assert stats["usage_percentage"] is None

    @pytest.mark.asyncio
    async def test_get_usage_stats_with_limit(self) -> None:
        provider = MockProvider([_text_result("ok")])
        agent = Agent(name="t", model="m", provider=provider)
        agent._token_usage = 40_000
        agent._context_window_limit = 128_000

        stats = agent.get_usage_stats()

        assert stats["usage_percentage"] == pytest.approx(0.3125)
        assert stats["usage_percentage"] is not None
        assert 0.0 <= stats["usage_percentage"] <= 1.0

    @pytest.mark.asyncio
    async def test_get_usage_stats_caps_at_one(self) -> None:
        provider = MockProvider([_text_result("ok")])
        agent = Agent(name="t", model="m", provider=provider)
        agent._token_usage = 200_000
        agent._context_window_limit = 128_000

        stats = agent.get_usage_stats()

        assert stats["usage_percentage"] == 1.0

    @pytest.mark.asyncio
    async def test_detect_context_window_limit_unknown_model(self) -> None:
        from unittest.mock import patch

        provider = MockProvider([_text_result("ok")])
        agent = Agent(name="t", model="unknown-model", provider=provider)

        with patch("litellm.get_model_info", side_effect=Exception("Model not found")):
            agent._detect_context_window_limit()

        assert agent._context_window_limit is None
        assert agent._context_window_detected


class TestAgentTokenCompaction:
    @pytest.mark.asyncio
    async def test_no_compaction_below_token_threshold(self) -> None:
        provider = MockProvider([_text_result("ok")])
        agent = Agent(name="test", model="m", provider=provider)
        agent._context_window_limit = 10_000
        agent._token_usage = 7_000
        agent._turns_since_compaction = 5
        agent._conversation_history = [
            Message(role="user", content="msg0"),
            Message(role="assistant", content="msg1"),
        ]

        result = await agent._maybe_compact_history()

        assert not result
        assert agent._turns_since_compaction == 6

    @pytest.mark.asyncio
    async def test_token_compaction_triggers_above_threshold(self) -> None:
        from unittest.mock import patch

        provider = MockProvider([_text_result("ok")])
        agent = Agent(name="test", model="m", provider=provider)
        agent._context_window_limit = 10_000
        agent._token_usage = 8_500
        agent._turns_since_compaction = 2
        agent._conversation_history = [Message(role="user", content=f"msg{i}") for i in range(5)]

        async def fake_compact_messages(
            messages: list[Message],
            provider: Any,
            threshold: int,
            keep_recent: int,
        ) -> list[Message]:
            return messages[-2:]

        with (
            patch(
                "sage.memory.compaction.compact_messages",
                new=fake_compact_messages,
            ),
            patch.object(agent, "_update_token_usage"),
        ):
            result = await agent._maybe_compact_history()

        assert result
        assert agent._turns_since_compaction == 0

    @pytest.mark.asyncio
    async def test_token_compaction_blocked_by_cooldown(self) -> None:
        provider = MockProvider([_text_result("ok")])
        agent = Agent(name="test", model="m", provider=provider)
        agent._context_window_limit = 10_000
        agent._token_usage = 9_000
        agent._turns_since_compaction = 1
        agent._conversation_history = [
            Message(role="user", content="msg0"),
            Message(role="assistant", content="msg1"),
        ]

        result = await agent._maybe_compact_history()

        assert not result

    @pytest.mark.asyncio
    async def test_message_count_fallback_when_no_limit(self) -> None:
        from unittest.mock import patch

        provider = MockProvider([_text_result("ok")])
        agent = Agent(name="test", model="m", provider=provider)
        agent._context_window_limit = None
        agent._compaction_threshold = 2
        agent._conversation_history = [Message(role="user", content=f"msg{i}") for i in range(5)]

        async def fake_compact_messages(
            messages: list[Message],
            provider: Any,
            threshold: int,
            keep_recent: int,
        ) -> list[Message]:
            return messages[-2:]

        with (
            patch(
                "sage.memory.compaction.compact_messages",
                new=fake_compact_messages,
            ),
            patch.object(agent, "_update_token_usage"),
        ):
            result = await agent._maybe_compact_history()

        assert result


class TestAgentPermissions:
    async def test_permission_deny_returns_error_to_model(self) -> None:
        """When a tool is denied, the error is fed back to the model."""
        from sage.permissions.base import PermissionAction
        from sage.permissions.policy import PolicyPermissionHandler, PermissionRule

        @tool
        def dangerous() -> str:
            """Dangerous tool."""
            return "should not execute"

        handler = PolicyPermissionHandler(
            rules=[PermissionRule(tool="dangerous", action=PermissionAction.DENY)],
            default=PermissionAction.ALLOW,
        )

        provider = MockProvider(
            [
                _tool_call_result([ToolCall(id="1", name="dangerous", arguments={})]),
                _text_result("I tried but it was denied."),
            ]
        )

        agent = Agent(
            name="test",
            model="gpt-4o",
            tools=[dangerous],
            provider=provider,
        )
        agent.tool_registry.set_permission_handler(handler)

        result = await agent.run("do dangerous thing")
        # The model should have received the permission error and responded.
        assert "denied" in result.lower() or result  # model saw the error

    async def test_permission_allow_executes_normally(self) -> None:
        from sage.permissions.base import PermissionAction
        from sage.permissions.policy import PolicyPermissionHandler

        @tool
        def safe_tool() -> str:
            """Safe tool."""
            return "safe result"

        handler = PolicyPermissionHandler(
            rules=[],
            default=PermissionAction.ALLOW,
        )

        provider = MockProvider(
            [
                _tool_call_result([ToolCall(id="1", name="safe_tool", arguments={})]),
                _text_result("Tool returned: safe result"),
            ]
        )

        agent = Agent(
            name="test",
            model="gpt-4o",
            tools=[safe_tool],
            provider=provider,
        )
        agent.tool_registry.set_permission_handler(handler)

        result = await agent.run("use safe tool")
        assert "safe result" in result


class TestAgentFromConfigWithPermissions:
    async def test_from_config_wires_permissions(self, tmp_path: Path) -> None:
        config_file = tmp_path / "AGENTS.md"
        config_file.write_text(
            textwrap.dedent("""\
            ---
            name: test
            model: gpt-4o
            permission:
              read: allow
            ---
            You are a test agent.
        """)
        )
        agent = Agent.from_config(str(config_file))
        assert agent.tool_registry._permission_handler is not None


class TestParallelToolExecution:
    """Tests for _execute_tool_calls with parallel_tool_execution flag."""

    def _make_agent(
        self,
        parallel: bool = True,
        tools: list[Any] | None = None,
        provider: Any | None = None,
    ) -> Agent:
        """Build a minimal Agent with the given parallel flag."""
        return Agent(
            name="parallel-test",
            model="test-model",
            tools=tools,
            provider=provider or MockProvider([_text_result("done")]),
            parallel_tool_execution=parallel,
        )

    @pytest.mark.asyncio
    async def test_parallel_tools_run_concurrently(self) -> None:
        """Three tools with asyncio.sleep should complete in roughly one sleep duration."""
        import time
        import asyncio
        from unittest.mock import patch

        DELAY = 0.1
        call_order: list[str] = []

        async def slow_tool(name: str) -> str:
            await asyncio.sleep(DELAY)
            call_order.append(name)
            return f"result-{name}"

        agent = self._make_agent(parallel=True)

        tool_calls = [
            ToolCall(id="tc_1", name="tool_a", arguments={"name": "a"}),
            ToolCall(id="tc_2", name="tool_b", arguments={"name": "b"}),
            ToolCall(id="tc_3", name="tool_c", arguments={"name": "c"}),
        ]

        async def fake_execute(name: str, arguments: dict[str, Any]) -> str:
            return await slow_tool(arguments["name"])

        messages: list[Message] = []
        with patch.object(agent.tool_registry, "execute", side_effect=fake_execute):
            start = time.monotonic()
            await agent._execute_tool_calls(tool_calls, messages)
            elapsed = time.monotonic() - start

        # All three ran, in order in the result messages.
        assert len(messages) == 3
        assert messages[0].tool_call_id == "tc_1"
        assert messages[1].tool_call_id == "tc_2"
        assert messages[2].tool_call_id == "tc_3"
        assert messages[0].content == "result-a"
        assert messages[1].content == "result-b"
        assert messages[2].content == "result-c"

        # Parallel: total time should be less than 3x the per-tool delay.
        assert elapsed < 3 * DELAY * 2.0, (
            f"Expected parallel execution (< {3 * DELAY * 2.0:.2f}s), got {elapsed:.3f}s"
        )

    @pytest.mark.asyncio
    async def test_error_in_one_tool_does_not_block_others(self) -> None:
        """An error in one tool should not prevent others from completing."""
        from unittest.mock import patch

        async def sometimes_fail(name: str, arguments: dict[str, Any]) -> str:
            if name == "fail_tool":
                raise RuntimeError("boom")
            return "ok"

        agent = self._make_agent(parallel=True)

        tool_calls = [
            ToolCall(id="tc_ok1", name="ok_tool", arguments={}),
            ToolCall(id="tc_fail", name="fail_tool", arguments={}),
            ToolCall(id="tc_ok2", name="ok_tool2", arguments={}),
        ]

        messages: list[Message] = []
        with patch.object(agent.tool_registry, "execute", side_effect=sometimes_fail):
            await agent._execute_tool_calls(tool_calls, messages)

        assert len(messages) == 3
        assert messages[0].content == "ok"
        assert "Error executing tool 'fail_tool'" in messages[1].content
        assert messages[2].content == "ok"

    @pytest.mark.asyncio
    async def test_sequential_mode_when_disabled(self) -> None:
        """When parallel_tool_execution=False, tools run sequentially (order preserved)."""
        import asyncio
        from unittest.mock import patch

        execution_order: list[str] = []

        async def ordered_execute(name: str, arguments: dict[str, Any]) -> str:
            execution_order.append(name)
            await asyncio.sleep(0)  # yield control to event loop
            return f"result-{name}"

        agent = self._make_agent(parallel=False)

        tool_calls = [
            ToolCall(id="tc_1", name="first", arguments={}),
            ToolCall(id="tc_2", name="second", arguments={}),
            ToolCall(id="tc_3", name="third", arguments={}),
        ]

        messages: list[Message] = []
        with patch.object(agent.tool_registry, "execute", side_effect=ordered_execute):
            await agent._execute_tool_calls(tool_calls, messages)

        # Sequential mode: tools execute in strict call order.
        assert execution_order == ["first", "second", "third"]
        assert len(messages) == 3
        assert messages[0].content == "result-first"
        assert messages[1].content == "result-second"
        assert messages[2].content == "result-third"

    @pytest.mark.asyncio
    async def test_permission_error_propagates(self) -> None:
        """SagePermissionError must not be swallowed by _safe_execute."""
        from unittest.mock import patch
        from sage.exceptions import PermissionError as SagePermissionError

        async def deny_all(name: str, arguments: dict[str, Any]) -> str:
            raise SagePermissionError("access denied")

        agent = self._make_agent(parallel=True)

        tool_calls = [ToolCall(id="tc_1", name="some_tool", arguments={})]
        messages: list[Message] = []

        with patch.object(agent.tool_registry, "execute", side_effect=deny_all):
            with pytest.raises(SagePermissionError, match="access denied"):
                await agent._execute_tool_calls(tool_calls, messages)

    @pytest.mark.asyncio
    async def test_permission_error_propagates_with_other_tools_in_parallel(self) -> None:
        """SagePermissionError from one tool must propagate even with other tools running."""
        from unittest.mock import patch
        from sage.exceptions import PermissionError as SagePermissionError

        async def selective_execute(name: str, arguments: dict) -> str:
            if name == "denied_tool":
                raise SagePermissionError("denied")
            return f"ok-{name}"

        agent = self._make_agent(parallel=True)
        tool_calls = [
            ToolCall(id="tc_1", name="allowed_1", arguments={}),
            ToolCall(id="tc_2", name="denied_tool", arguments={}),
            ToolCall(id="tc_3", name="allowed_2", arguments={}),
        ]
        messages: list[Message] = []
        with patch.object(agent.tool_registry, "execute", side_effect=selective_execute):
            with pytest.raises(SagePermissionError, match="denied"):
                await agent._execute_tool_calls(tool_calls, messages)

    @pytest.mark.asyncio
    async def test_parallel_tool_execution_default_is_true(self) -> None:
        """Agent defaults to parallel_tool_execution=True."""
        agent = Agent(name="default-test", model="test-model")
        assert agent.parallel_tool_execution is True

    @pytest.mark.asyncio
    async def test_result_order_preserved_in_parallel_mode(self) -> None:
        """asyncio.gather preserves order — messages must match tool_calls order."""
        import asyncio
        from unittest.mock import patch

        # Tools complete in reverse order (last tool finishes first).
        async def reverse_latency(name: str, arguments: dict[str, Any]) -> str:
            delays = {"slow": 0.05, "medium": 0.02, "fast": 0.0}
            await asyncio.sleep(delays.get(name, 0))
            return f"done-{name}"

        agent = self._make_agent(parallel=True)

        tool_calls = [
            ToolCall(id="id_slow", name="slow", arguments={}),
            ToolCall(id="id_medium", name="medium", arguments={}),
            ToolCall(id="id_fast", name="fast", arguments={}),
        ]

        messages: list[Message] = []
        with patch.object(agent.tool_registry, "execute", side_effect=reverse_latency):
            await agent._execute_tool_calls(tool_calls, messages)

        # Despite different completion times, messages must appear in call order.
        assert messages[0].tool_call_id == "id_slow"
        assert messages[0].content == "done-slow"
        assert messages[1].tool_call_id == "id_medium"
        assert messages[1].content == "done-medium"
        assert messages[2].tool_call_id == "id_fast"
        assert messages[2].content == "done-fast"

    @pytest.mark.asyncio
    async def test_permission_error_propagates_in_sequential_mode(self) -> None:
        """SagePermissionError must propagate in sequential (parallel=False) mode too."""
        from unittest.mock import patch

        from sage.exceptions import PermissionError as SagePermissionError

        async def deny_all(name: str, arguments: dict) -> str:
            raise SagePermissionError("denied")

        agent = self._make_agent(parallel=False)
        tool_calls = [ToolCall(id="tc_1", name="some_tool", arguments={})]
        messages: list[Message] = []
        with patch.object(agent.tool_registry, "execute", side_effect=deny_all):
            with pytest.raises(SagePermissionError, match="denied"):
                await agent._execute_tool_calls(tool_calls, messages)


# ── Memory Tool Unification Tests ─────────────────────────────────────


class TestMemoryToolUnification:
    """Tests for memory tool unification — semantic backend overrides JSON tools."""

    @pytest.mark.asyncio
    async def test_semantic_memory_tools_registered_when_memory_backend_set(self) -> None:
        """When memory backend is configured, tool registry gets semantic closures."""
        from unittest.mock import AsyncMock, MagicMock

        from sage.memory.base import MemoryEntry

        # Build a mock memory backend.
        mock_memory = MagicMock()
        mock_memory.store = AsyncMock(return_value="mock-id")
        mock_memory.recall = AsyncMock(
            return_value=[
                MemoryEntry(id="1", content="project: apollo", metadata={"key": "project"})
            ]
        )

        # Build agent with the mock memory injected.
        provider = MockProvider([_text_result("done")])
        agent = Agent(
            name="mem-test",
            model="test-model",
            provider=provider,
            memory=mock_memory,
        )

        # Register semantic tools (mirrors what _from_agent_config does).
        from sage.tools.decorator import tool as _tool

        @_tool
        async def memory_store(key: str, value: str) -> str:  # noqa: F811
            """Store a key-value pair in the agent's semantic memory backend."""
            await mock_memory.store(f"{key}: {value}", metadata={"key": key})
            return f"Stored: {key}"

        @_tool
        async def memory_recall(query: str) -> str:  # noqa: F811
            """Recall entries from the agent's semantic memory backend."""
            entries = await mock_memory.recall(query)
            if not entries:
                return f"No matches for: {query}"
            return "\n".join(f"- {e.content}" for e in entries)

        agent.tool_registry.register(memory_store)
        agent.tool_registry.register(memory_recall)

        # Verify that memory_store calls memory.store().
        store_result = await agent.tool_registry.execute(
            "memory_store", {"key": "project", "value": "apollo"}
        )
        assert store_result == "Stored: project"
        mock_memory.store.assert_called_once_with("project: apollo", metadata={"key": "project"})

        # Verify that memory_recall calls memory.recall().
        recall_result = await agent.tool_registry.execute("memory_recall", {"query": "project"})
        assert "project: apollo" in recall_result
        mock_memory.recall.assert_called_once_with("project")

    @pytest.mark.asyncio
    async def test_json_memory_tools_used_without_backend(self) -> None:
        """Without a memory backend, the JSON memory_store / memory_recall are still available."""
        import warnings

        provider = MockProvider([_text_result("done")])
        agent = Agent(
            name="no-mem-test",
            model="test-model",
            provider=provider,
        )

        # Manually load the builtin JSON memory tools.
        agent.tool_registry.load_from_module("memory_store")
        agent.tool_registry.load_from_module("memory_recall")

        # Both tools should be registered.
        schemas = {s.name for s in agent.tool_registry.get_schemas()}
        assert "memory_store" in schemas
        assert "memory_recall" in schemas

        # Calling them should emit DeprecationWarning (JSON backend).
        import os
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp_dir:
            mem_path = os.path.join(tmp_dir, "mem.json")
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                with patch.dict(os.environ, {"SAGE_MEMORY_PATH": mem_path}):
                    await agent.tool_registry.execute("memory_store", {"key": "k", "value": "v"})
            assert any(issubclass(warning.category, DeprecationWarning) for warning in w)


# ── Memory Relevance Filter Tests ─────────────────────────────────────────────


class TestMemoryRelevanceFilter:
    """Tests for relevance filtering in _store_memory()."""

    def _make_agent_with_memory_config(
        self,
        mock_memory: Any,
        relevance_filter: str = "length",
        min_exchange_length: int = 100,
        relevance_threshold: float = 0.5,
        provider: Any = None,
    ) -> Agent:
        """Build an Agent with a mock memory backend and a custom _memory_config."""

        from sage.config import MemoryConfig

        mem_config = MemoryConfig(
            relevance_filter=relevance_filter,  # type: ignore[arg-type]
            min_exchange_length=min_exchange_length,
            relevance_threshold=relevance_threshold,
        )
        if provider is None:
            provider = MockProvider([])
        agent = Agent(
            name="filter-test",
            model="test-model",
            memory=mock_memory,
            provider=provider,
        )
        agent._memory_config = mem_config
        return agent

    @pytest.mark.asyncio
    async def test_length_filter_skips_short_exchanges(self) -> None:
        """Length filter: short exchange (< min_exchange_length) is NOT stored."""
        from unittest.mock import AsyncMock

        mock_memory = AsyncMock()
        mock_memory.initialize = AsyncMock()
        mock_memory.recall = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock(return_value="mem-1")

        agent = self._make_agent_with_memory_config(
            mock_memory,
            relevance_filter="length",
            min_exchange_length=100,
        )

        # Build a short input/output pair that results in content < 100 chars
        short_input = "Hi"
        short_output = "Hello"
        # "User: Hi\nAssistant: Hello" = 25 chars, well below 100
        await agent._store_memory(short_input, short_output)

        mock_memory.store.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_length_filter_stores_long_exchanges(self) -> None:
        """Length filter: long exchange (>= min_exchange_length) IS stored."""
        from unittest.mock import AsyncMock

        mock_memory = AsyncMock()
        mock_memory.initialize = AsyncMock()
        mock_memory.recall = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock(return_value="mem-2")

        agent = self._make_agent_with_memory_config(
            mock_memory,
            relevance_filter="length",
            min_exchange_length=100,
        )

        # Build input/output that together exceed 100 chars
        long_input = "What is the best way to learn Python programming for beginners?"
        long_output = "Start with the official Python tutorial and practice with small projects."
        # "User: <long_input>\nAssistant: <long_output>" far exceeds 100 chars
        await agent._store_memory(long_input, long_output)

        mock_memory.store.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_none_filter_stores_everything(self) -> None:
        """None filter: even very short exchanges are stored."""
        from unittest.mock import AsyncMock

        mock_memory = AsyncMock()
        mock_memory.initialize = AsyncMock()
        mock_memory.recall = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock(return_value="mem-3")

        agent = self._make_agent_with_memory_config(
            mock_memory,
            relevance_filter="none",
            min_exchange_length=100,
        )

        # Short exchange that would be skipped by "length" filter
        await agent._store_memory("OK", "Sure")

        mock_memory.store.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_llm_filter_skips_low_score(self) -> None:
        """LLM filter: provider returns a low score -> exchange is NOT stored."""
        from unittest.mock import AsyncMock

        mock_memory = AsyncMock()
        mock_memory.initialize = AsyncMock()
        mock_memory.recall = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock(return_value="mem-4")

        # Provider returns "0.2" for the scoring call
        scoring_provider = MockProvider([_text_result("0.2")])

        agent = self._make_agent_with_memory_config(
            mock_memory,
            relevance_filter="llm",
            relevance_threshold=0.5,
            provider=scoring_provider,
        )

        await agent._store_memory("Hello", "Hi there")

        mock_memory.store.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_llm_filter_stores_high_score(self) -> None:
        """LLM filter: provider returns a high score -> exchange IS stored."""
        from unittest.mock import AsyncMock

        mock_memory = AsyncMock()
        mock_memory.initialize = AsyncMock()
        mock_memory.recall = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock(return_value="mem-5")

        # Provider returns "0.8" for the scoring call
        scoring_provider = MockProvider([_text_result("0.8")])

        agent = self._make_agent_with_memory_config(
            mock_memory,
            relevance_filter="llm",
            relevance_threshold=0.5,
            provider=scoring_provider,
        )

        await agent._store_memory(
            "What is the capital of France?",
            "The capital of France is Paris.",
        )

        mock_memory.store.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_llm_filter_defaults_to_store_on_parse_failure(self) -> None:
        """LLM filter: when provider returns unparseable text, exchange is stored (fail-safe)."""
        from unittest.mock import AsyncMock

        mock_memory = AsyncMock()
        mock_memory.initialize = AsyncMock()
        mock_memory.recall = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock(return_value="mem-6")

        # Provider returns a non-numeric response
        scoring_provider = MockProvider([_text_result("not a number")])

        agent = self._make_agent_with_memory_config(
            mock_memory,
            relevance_filter="llm",
            relevance_threshold=0.5,
            provider=scoring_provider,
        )

        await agent._store_memory(
            "What is the answer?",
            "The answer is 42.",
        )

        # Fail-safe: parse failure defaults to score=1.0, which is >= 0.5, so stored
        mock_memory.store.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_store_memory_no_memory_config_stores_everything(self) -> None:
        """When _memory_config is None (direct Agent() construction), all exchanges are stored."""
        from unittest.mock import AsyncMock

        mock_memory: Any = AsyncMock()
        mock_memory.store = AsyncMock(return_value="id-1")

        # Construct the agent directly — _memory_config stays None
        agent = Agent(
            name="direct",
            model="test-model",
            memory=mock_memory,
            provider=MockProvider([]),
        )
        assert agent._memory_config is None

        # Short exchange that length-filter would skip
        short_input = "Hi"
        short_output = "Hello"
        await agent._store_memory(short_input, short_output)

        # Must be stored regardless — backward compat fallback is "none"
        mock_memory.store.assert_awaited_once()


# ── Structured Output Tests ────────────────────────────────────────────────


class TestStructuredOutput:
    """Tests for Agent.run() with response_model for structured Pydantic output."""

    class _UserInfo:
        pass  # defined below as a proper Pydantic model

    # We define the model here so it's accessible in all test methods.
    from pydantic import BaseModel as _BaseModel

    class _UserInfo(_BaseModel):
        name: str
        age: int

    @pytest.mark.asyncio
    async def test_run_without_response_model_returns_str(self) -> None:
        """run() without response_model returns a plain str as before."""
        provider = MockProvider([_text_result("Hello, world!")])
        agent = Agent(name="test", model="test-model", provider=provider)

        result = await agent.run("Say hello")

        assert isinstance(result, str)
        assert result == "Hello, world!"

    @pytest.mark.asyncio
    async def test_run_with_response_model_returns_parsed_object(self) -> None:
        """run() with response_model parses JSON and returns the model instance."""
        provider = MockProvider([_text_result('{"name": "Alice", "age": 30}')])
        agent = Agent(name="test", model="test-model", provider=provider)

        result = await agent.run("Give me user info", response_model=TestStructuredOutput._UserInfo)

        assert isinstance(result, TestStructuredOutput._UserInfo)
        assert result.name == "Alice"
        assert result.age == 30

    @pytest.mark.asyncio
    async def test_run_schema_injected_in_system_message(self) -> None:
        """When response_model is set, a schema system message is injected."""
        provider = MockProvider([_text_result('{"name": "Bob", "age": 25}')])
        agent = Agent(name="test", model="test-model", provider=provider)

        await agent.run("Give me user info", response_model=TestStructuredOutput._UserInfo)

        # Inspect the messages sent to the provider on the first (only) call.
        call_messages: list[Message] = provider.call_args[0]["messages"]
        system_messages = [m for m in call_messages if m.role == "system"]

        # At least one system message should mention JSON schema.
        schema_messages = [m for m in system_messages if "JSON" in (m.content or "")]
        assert len(schema_messages) >= 1

        # The schema message should contain the field names from _UserInfo.
        schema_content = schema_messages[0].content or ""
        assert "name" in schema_content
        assert "age" in schema_content

    @pytest.mark.asyncio
    async def test_run_invalid_json_raises_validation_error(self) -> None:
        """If provider returns invalid JSON, model_validate_json raises ValidationError."""
        from pydantic import ValidationError

        provider = MockProvider([_text_result("not valid json at all")])
        agent = Agent(name="test", model="test-model", provider=provider)

        with pytest.raises(ValidationError):
            await agent.run("Give me user info", response_model=TestStructuredOutput._UserInfo)

    @pytest.mark.asyncio
    async def test_run_with_markdown_fenced_json(self) -> None:
        """Markdown code fences around JSON are stripped before parsing."""
        fenced = '```json\n{"name": "Charlie", "age": 42}\n```'
        provider = MockProvider([_text_result(fenced)])
        agent = Agent(name="test", model="test-model", provider=provider)

        result = await agent.run("Give me user info", response_model=TestStructuredOutput._UserInfo)

        assert result.name == "Charlie"
        assert result.age == 42

    @pytest.mark.asyncio
    async def test_run_schema_inserted_before_user_message(self) -> None:
        """The schema system message appears before the user message in the list."""
        provider = MockProvider([_text_result('{"name": "Dana", "age": 28}')])
        # Give agent a body so it generates a system message naturally.
        agent = Agent(
            name="test",
            model="test-model",
            provider=provider,
            body="You are a helpful assistant.",
        )

        await agent.run("Give me user info", response_model=TestStructuredOutput._UserInfo)

        call_messages: list[Message] = provider.call_args[0]["messages"]
        # Find the index of the schema system message and the user message.
        schema_idx = next(
            (
                i
                for i, m in enumerate(call_messages)
                if m.role == "system" and "JSON" in (m.content or "")
            ),
            None,
        )
        user_idx = next(
            (i for i, m in enumerate(call_messages) if m.role == "user"),
            None,
        )

        assert schema_idx is not None, "Schema system message not found"
        assert user_idx is not None, "User message not found"
        assert schema_idx < user_idx, "Schema message must appear before user message"

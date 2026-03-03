from __future__ import annotations

from dataclasses import dataclass

from sage.config import AgentPromptMetadata
from sage.prompts.dynamic_builder import (
    DELEGATION_PLACEHOLDER,
    build_delegation_table,
    build_orchestrator_prompt,
    resolve_placeholder,
)


@dataclass
class _StubAgent:
    name: str = ""
    description: str = ""
    _prompt_metadata: AgentPromptMetadata | None = None


class TestBuildDelegationTable:
    def test_empty_subagents(self) -> None:
        assert build_delegation_table({}) == ""

    def test_single_agent_no_metadata(self) -> None:
        agents = {"helper": _StubAgent(name="helper", description="A helper")}
        table = build_delegation_table(agents)
        assert "| **helper** |" in table
        assert "A helper" in table
        lines = table.strip().splitlines()
        assert len(lines) == 3  # header + separator + 1 row

    def test_single_agent_with_metadata(self) -> None:
        meta = AgentPromptMetadata(
            cost="expensive",
            triggers=["debug", "architecture"],
            use_when=["complex problems"],
            avoid_when=["trivial tasks"],
        )
        agents = {
            "oracle": _StubAgent(name="oracle", description="Consultant", _prompt_metadata=meta)
        }
        table = build_delegation_table(agents)
        assert "expensive" in table
        assert "debug, architecture" in table
        assert "complex problems" in table
        assert "trivial tasks" in table

    def test_multiple_agents_sorted(self) -> None:
        agents = {
            "zeta": _StubAgent(name="zeta", description="Last"),
            "alpha": _StubAgent(name="alpha", description="First"),
        }
        table = build_delegation_table(agents)
        lines = table.strip().splitlines()
        assert "alpha" in lines[2]
        assert "zeta" in lines[3]

    def test_missing_description_shows_dash(self) -> None:
        agents = {"bare": _StubAgent(name="bare")}
        table = build_delegation_table(agents)
        row = [line for line in table.splitlines() if "bare" in line][0]
        assert "—" in row

    def test_metadata_defaults(self) -> None:
        meta = AgentPromptMetadata()
        agents = {"a": _StubAgent(name="a", description="d", _prompt_metadata=meta)}
        table = build_delegation_table(agents)
        assert "cheap" in table  # default cost


class TestBuildOrchestratorPrompt:
    def test_empty_subagents(self) -> None:
        assert build_orchestrator_prompt({}) == ""

    def test_includes_header_and_table(self) -> None:
        agents = {"x": _StubAgent(name="x", description="X agent")}
        prompt = build_orchestrator_prompt(agents)
        assert prompt.startswith("## Available Agents")
        assert "delegate" in prompt
        assert "| **x** |" in prompt


class TestResolvePlaceholder:
    def test_no_placeholder_returns_body_unchanged(self) -> None:
        body = "You are a helpful assistant."
        assert resolve_placeholder(body, {}) == body

    def test_placeholder_replaced_with_empty_subagents(self) -> None:
        body = f"Preamble\n\n{DELEGATION_PLACEHOLDER}\n\nPostamble"
        result = resolve_placeholder(body, {})
        assert DELEGATION_PLACEHOLDER not in result
        assert "Preamble" in result
        assert "Postamble" in result

    def test_placeholder_replaced_with_agents(self) -> None:
        meta = AgentPromptMetadata(cost="free", triggers=["search"])
        agents = {
            "finder": _StubAgent(name="finder", description="Finds things", _prompt_metadata=meta)
        }
        body = f"System prompt.\n\n{DELEGATION_PLACEHOLDER}"
        result = resolve_placeholder(body, agents)
        assert DELEGATION_PLACEHOLDER not in result
        assert "## Available Agents" in result
        assert "finder" in result
        assert "free" in result

    def test_placeholder_only_replaced_once(self) -> None:
        body = f"{DELEGATION_PLACEHOLDER}\n{DELEGATION_PLACEHOLDER}"
        agents = {"a": _StubAgent(name="a", description="d")}
        result = resolve_placeholder(body, agents)
        assert result.count("## Available Agents") == 2  # str.replace replaces all


class TestAgentPromptMetadata:
    def test_defaults(self) -> None:
        meta = AgentPromptMetadata()
        assert meta.cost == "cheap"
        assert meta.triggers == []
        assert meta.use_when == []
        assert meta.avoid_when == []

    def test_explicit_values(self) -> None:
        meta = AgentPromptMetadata(
            cost="expensive",
            triggers=["debug"],
            use_when=["hard problems"],
            avoid_when=["simple tasks"],
        )
        assert meta.cost == "expensive"
        assert meta.triggers == ["debug"]

    def test_extra_fields_forbidden(self) -> None:
        import pytest

        with pytest.raises(Exception):
            AgentPromptMetadata(cost="cheap", unknown_field="bad")  # type: ignore[call-arg]

from __future__ import annotations

import pytest

from sage.tools.agent_tools.delegation import register_delegation_tools
from sage.tools.registry import ToolRegistry


class _Subagent:
    def __init__(self, description: str = "") -> None:
        self.description = description


class _AgentStub:
    def __init__(self) -> None:
        self.subagents = {
            "alpha": _Subagent(),
            "beta": _Subagent("Beta helper"),
        }
        self.tool_registry = ToolRegistry()
        self.calls: list[tuple[str, str, str | None, str | None]] = []

    async def delegate(
        self,
        agent_name: str,
        task: str,
        session_id: str | None = None,
        category: str | None = None,
    ) -> str:
        self.calls.append((agent_name, task, session_id, category))
        return "ok"


@pytest.mark.asyncio
async def test_register_delegation_tools_registers_delegate_schema() -> None:
    agent = _AgentStub()
    register_delegation_tools(agent)

    schemas = {s.name: s for s in agent.tool_registry.get_schemas()}
    assert "delegate" in schemas
    delegate_schema = schemas["delegate"]
    params = delegate_schema.parameters
    assert params["required"] == ["agent_name", "task"]
    assert set(params["properties"]["agent_name"]["enum"]) == {"alpha", "beta"}
    assert "beta: Beta helper" in delegate_schema.description

    result = await agent.tool_registry.execute(
        "delegate",
        {
            "agent_name": "alpha",
            "task": "do work",
            "session_id": "s1",
            "category": "quick",
        },
    )
    assert result == "ok"
    assert agent.calls == [("alpha", "do work", "s1", "quick")]

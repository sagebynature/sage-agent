from __future__ import annotations

from types import SimpleNamespace

from sage.hooks.registry import HookRegistry
from sage.tools.agent_tools.planning import register_planning_tools
from sage.tools.registry import ToolRegistry


class _AgentStub:
    def __init__(self) -> None:
        self.tool_registry = ToolRegistry()
        self._hook_registry = HookRegistry()


def test_register_planning_tools_registers_all_six_with_review_enabled() -> None:
    agent = _AgentStub()
    config = SimpleNamespace(
        planning=SimpleNamespace(
            review=SimpleNamespace(enabled=True, prompt=None, max_iterations=3)
        )
    )

    register_planning_tools(agent, config)

    tool_names = {schema.name for schema in agent.tool_registry.get_schemas()}
    assert tool_names.issuperset(
        {
            "plan_create",
            "plan_status",
            "plan_update",
            "plan_review",
            "notepad_write",
            "notepad_read",
        }
    )

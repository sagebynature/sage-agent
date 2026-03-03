from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock


from sage.hooks.base import HookEvent
from sage.hooks.builtin.plan_analyzer import make_plan_analyzer
from sage.planning.state import PlanState, PlanTask


def _make_plan_data(analysis: str | None = None) -> dict[str, Any]:
    plan = PlanState(
        plan_name="test",
        description="test plan",
        tasks=[PlanTask(description="step 1"), PlanTask(description="step 2")],
    )
    agent = AsyncMock()
    agent.provider.complete.return_value = AsyncMock(content="Looks good overall.")
    return {"plan": plan, "agent": agent, "analysis": analysis}


class TestMakePlanAnalyzer:
    async def test_populates_analysis(self) -> None:
        hook = make_plan_analyzer()
        data = _make_plan_data()
        result = await hook(HookEvent.ON_PLAN_CREATED, data)
        assert result["analysis"] == "Looks good overall."

    async def test_calls_provider_complete(self) -> None:
        hook = make_plan_analyzer()
        data = _make_plan_data()
        await hook(HookEvent.ON_PLAN_CREATED, data)
        data["agent"].provider.complete.assert_called_once()

    async def test_ignores_wrong_event(self) -> None:
        hook = make_plan_analyzer()
        data = _make_plan_data()
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result["analysis"] is None

    async def test_custom_prompt_used(self) -> None:
        custom = "Check {plan_name}: {description}\n{tasks}"
        hook = make_plan_analyzer(prompt=custom)
        data = _make_plan_data()
        await hook(HookEvent.ON_PLAN_CREATED, data)
        call_args = data["agent"].provider.complete.call_args
        msg_content = (
            call_args.kwargs["messages"][0].content
            if call_args.kwargs
            else call_args[1]["messages"][0].content
            if len(call_args) > 1
            else call_args[0][0][0].content
        )
        assert "Check test" in msg_content

    async def test_returns_dict(self) -> None:
        hook = make_plan_analyzer()
        data = _make_plan_data()
        result = await hook(HookEvent.ON_PLAN_CREATED, data)
        assert isinstance(result, dict)
        assert "plan" in result
        assert "agent" in result

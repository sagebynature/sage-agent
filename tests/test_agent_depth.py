from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from sage.agent import Agent
from sage.exceptions import ToolError


class TestAgentDepthConfig:
    def test_init_max_depth_defaults_to_three(self) -> None:
        agent = Agent(name="test", model="gpt-4o")
        assert agent.max_depth == 3

    def test_init_current_depth_defaults_to_zero(self) -> None:
        agent = Agent(name="test", model="gpt-4o")
        assert agent._current_depth == 0


class TestAgentDelegationDepth:
    @pytest.mark.asyncio
    async def test_delegate_raises_tool_error_when_depth_exceeded(self) -> None:
        subagent = Agent(name="worker", model="gpt-4o")
        parent = Agent(
            name="parent",
            model="gpt-4o",
            subagents={"worker": subagent},
            max_depth=1,
            _current_depth=1,
        )

        with pytest.raises(ToolError, match=r"Max delegation depth \(1\) exceeded"):
            await parent.delegate("worker", "run task")

    @pytest.mark.asyncio
    async def test_delegate_propagates_depth_to_subagent(self) -> None:
        subagent = Agent(name="worker", model="gpt-4o")
        subagent.run = AsyncMock(return_value="ok")  # type: ignore[method-assign]
        parent = Agent(
            name="parent",
            model="gpt-4o",
            subagents={"worker": subagent},
            max_depth=5,
            _current_depth=2,
        )

        result = await parent.delegate("worker", "run task")

        assert result == "ok"
        assert subagent._current_depth == 3
        subagent.run.assert_awaited_once_with("run task")

    @pytest.mark.asyncio
    async def test_delegate_allows_within_depth_limit(self) -> None:
        subagent = Agent(name="worker", model="gpt-4o")
        subagent.run = AsyncMock(return_value="done")  # type: ignore[method-assign]
        parent = Agent(
            name="parent",
            model="gpt-4o",
            subagents={"worker": subagent},
            max_depth=2,
            _current_depth=1,
        )

        result = await parent.delegate("worker", "safe task")

        assert result == "done"
        subagent.run.assert_awaited_once_with("safe task")

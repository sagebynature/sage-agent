"""Tests for EvalRunner — focuses on model override propagation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sage.eval.runner import EvalRunner
from sage.eval.suite import EvalSettings, TestCase, TestSuite
from sage.models import Usage


def _make_suite(agent_path: str = "dummy.md", models: list[str] | None = None) -> TestSuite:
    return TestSuite(
        name="test-suite",
        agent=agent_path,
        settings=EvalSettings(models=models or ["gpt-4o"], timeout=30.0),
        test_cases=[
            TestCase(id="tc-1", input="hello", assertions=[]),
        ],
        suite_dir=".",
    )


def _mock_agent(config_model: str = "original-model") -> MagicMock:
    """Return a mock Agent with a provider that has a .model attribute."""
    agent = MagicMock()
    agent.model = config_model
    provider = MagicMock()
    provider.model = config_model
    agent.provider = provider
    agent.cumulative_usage = Usage(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cost=0.001,
    )
    agent.run = AsyncMock(return_value="ok")
    agent.close = AsyncMock()
    agent.tool_registry = MagicMock()
    agent.tool_registry.execute = AsyncMock(return_value="tool result")
    return agent


@pytest.mark.asyncio
async def test_runner_overrides_provider_model():
    """EvalRunner must update agent.provider.model, not just agent.model.

    Regression test for the bug where agent.model was overridden but
    agent.provider.model was left pointing at the original config model,
    causing all API calls to use the wrong model and giving incorrect costs.
    """
    suite = _make_suite(models=["expensive-model"])
    runner = EvalRunner(suite, model="expensive-model")

    agent = _mock_agent(config_model="cheap-model")

    with patch("sage.agent.Agent") as MockAgent:
        MockAgent.from_config.return_value = agent
        await runner._run_case(suite.test_cases[0])

    # Both agent.model and agent.provider.model must be set to the runner model.
    assert agent.model == "expensive-model"
    assert agent.provider.model == "expensive-model"


@pytest.mark.asyncio
async def test_runner_provider_model_differs_from_config():
    """Provider model must reflect the overridden model, not the config model."""
    suite = _make_suite(models=["model-b"])
    runner = EvalRunner(suite, model="model-b")

    agent = _mock_agent(config_model="model-a")

    with patch("sage.agent.Agent") as MockAgent:
        MockAgent.from_config.return_value = agent
        await runner._run_case(suite.test_cases[0])

    assert agent.provider.model == "model-b"
    assert agent.provider.model != "model-a"

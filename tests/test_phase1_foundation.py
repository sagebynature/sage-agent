"""Tests for Phase 1 Foundation features."""

from __future__ import annotations

from sage.agent import Agent
from sage.config import AgentConfig, CategoryConfig, ModelParams
from sage.main_config import MainConfig
from sage.models import CompletionResult, Message, Usage


class MockProvider:
    """Minimal mock provider for testing."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = list(responses or ["Mock response"])
        self._call_count = 0
        self.model = "mock-model"

    async def complete(self, messages, tools=None):
        idx = min(self._call_count, len(self.responses) - 1)
        self._call_count += 1
        return CompletionResult(
            message=Message(role="assistant", content=self.responses[idx]),
            usage=Usage(),
        )


class TestSessionContinuity:
    """Tests for session continuity in delegation."""

    async def test_delegate_without_session_id_returns_raw_result(self) -> None:
        sub = Agent(name="sub", model="mock", provider=MockProvider())
        parent = Agent(name="parent", model="mock", provider=MockProvider(), subagents={"sub": sub})
        result = await parent.delegate("sub", "hello")
        assert result == "Mock response"
        assert "[Session:" not in result

    async def test_delegate_with_session_id_returns_prefixed_result(self) -> None:
        sub = Agent(name="sub", model="mock", provider=MockProvider())
        parent = Agent(name="parent", model="mock", provider=MockProvider(), subagents={"sub": sub})
        result = await parent.delegate("sub", "hello", session_id="test-session")
        assert "[Session: test-session]" in result
        assert "Mock response" in result

    async def test_delegate_with_session_id_resumes(self) -> None:
        sub = Agent(name="sub", model="mock", provider=MockProvider(["first", "second"]))
        parent = Agent(name="parent", model="mock", provider=MockProvider(), subagents={"sub": sub})

        result1 = await parent.delegate("sub", "first task", session_id="resume-test")
        assert "[Session: resume-test]" in result1

        result2 = await parent.delegate("sub", "second task", session_id="resume-test")
        assert "[Session: resume-test]" in result2


class TestCategoryRouting:
    """Tests for category-based model routing."""

    def test_category_config_in_main_config(self) -> None:
        cfg = MainConfig(
            categories={
                "quick": CategoryConfig(model="gpt-4o-mini"),
                "deep": CategoryConfig(
                    model="gpt-4o",
                    model_params=ModelParams(temperature=0.2),
                ),
            }
        )
        assert cfg.categories["quick"].model == "gpt-4o-mini"
        assert cfg.categories["deep"].model_params.temperature == 0.2

    def test_main_config_no_categories_default(self) -> None:
        cfg = MainConfig()
        assert cfg.categories == {}


class TestToolRestrictionsConfig:
    """Tests for tool restriction fields on AgentConfig."""

    def test_agent_config_accepts_allowed_tools(self) -> None:
        cfg = AgentConfig(name="test", model="gpt-4o", allowed_tools=["file_read", "shell"])
        assert cfg.allowed_tools == ["file_read", "shell"]

    def test_agent_config_accepts_blocked_tools(self) -> None:
        cfg = AgentConfig(name="test", model="gpt-4o", blocked_tools=["shell"])
        assert cfg.blocked_tools == ["shell"]

    def test_agent_config_defaults_none(self) -> None:
        cfg = AgentConfig(name="test", model="gpt-4o")
        assert cfg.allowed_tools is None
        assert cfg.blocked_tools is None

"""Tests for the configurable pre-response research phase."""

from __future__ import annotations

from typing import Any

import pytest

from sage.models import CompletionResult, Message, ToolCall, ToolSchema, Usage
from sage.research import ResearchConfig, ResearchTrigger, run_research, should_research
from sage.tools.registry import ToolRegistry


# ── Helpers ───────────────────────────────────────────────────────────


def _make_result(content: str, tool_calls: list[ToolCall] | None = None) -> CompletionResult:
    """Build a minimal CompletionResult with given content."""
    return CompletionResult(
        message=Message(role="assistant", content=content, tool_calls=tool_calls),
        usage=Usage(),
    )


class MockProvider:
    """Minimal mock provider whose ``complete`` method can be pre-programmed."""

    def __init__(self, responses: list[CompletionResult]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        **kwargs: Any,
    ) -> CompletionResult:
        result = self._responses[self._call_count]
        self._call_count += 1
        return result

    async def stream(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError

    async def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover
        raise NotImplementedError


# ── should_research tests ─────────────────────────────────────────────


class TestShouldResearchNever:
    """NEVER trigger: always returns False regardless of query."""

    def test_never_with_empty_query(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.NEVER)
        assert should_research("", config) is False

    def test_never_with_question_query(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.NEVER)
        assert should_research("What is the capital of France?", config) is False

    def test_never_with_long_query(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.NEVER, min_length=10)
        long_query = "a" * 200
        assert should_research(long_query, config) is False


class TestShouldResearchAlways:
    """ALWAYS trigger: always returns True regardless of query."""

    def test_always_with_empty_query(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.ALWAYS)
        assert should_research("", config) is True

    def test_always_with_short_query(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.ALWAYS)
        assert should_research("hi", config) is True

    def test_always_with_any_query(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.ALWAYS)
        assert should_research("Do this now.", config) is True


class TestShouldResearchKeywords:
    """KEYWORDS trigger: True when any keyword appears in query (case-insensitive)."""

    def test_keyword_present_exact_case(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.KEYWORDS, keywords=["python", "rust"])
        assert should_research("Tell me about python programming.", config) is True

    def test_keyword_present_uppercase(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.KEYWORDS, keywords=["python"])
        assert should_research("PYTHON is great!", config) is True

    def test_keyword_present_mixed_case(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.KEYWORDS, keywords=["Python"])
        assert should_research("i love python", config) is True

    def test_keyword_absent(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.KEYWORDS, keywords=["python", "rust"])
        assert should_research("Tell me about Go programming.", config) is False

    def test_empty_keywords_list(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.KEYWORDS, keywords=[])
        assert should_research("Tell me about anything.", config) is False

    def test_multiple_keywords_only_one_present(self) -> None:
        config = ResearchConfig(
            trigger=ResearchTrigger.KEYWORDS, keywords=["alpha", "beta", "gamma"]
        )
        assert should_research("I need info on beta testing.", config) is True


class TestShouldResearchLength:
    """LENGTH trigger: True when len(query) > min_length."""

    def test_query_above_min_length(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.LENGTH, min_length=10)
        assert should_research("This query is definitely longer than ten chars.", config) is True

    def test_query_exactly_at_min_length_is_false(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.LENGTH, min_length=10)
        assert should_research("a" * 10, config) is False  # equal is NOT greater than

    def test_query_below_min_length(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.LENGTH, min_length=100)
        assert should_research("short", config) is False

    def test_default_min_length(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.LENGTH)
        assert config.min_length == 100
        assert should_research("a" * 50, config) is False
        assert should_research("a" * 101, config) is True


class TestShouldResearchQuestion:
    """QUESTION trigger: True for queries ending with '?' or starting with question words."""

    def test_ends_with_question_mark(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.QUESTION)
        assert should_research("Is this working?", config) is True

    def test_ends_with_question_mark_whitespace(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.QUESTION)
        assert should_research("  Is this working?  ", config) is True

    @pytest.mark.parametrize(
        "query",
        [
            "Who invented the telephone?",
            "What is quantum entanglement?",
            "Where is the nearest hospital?",
            "When did World War II end?",
            "Why does the sky appear blue?",
            "How does photosynthesis work?",
        ],
    )
    def test_starts_with_question_word(self, query: str) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.QUESTION)
        assert should_research(query, config) is True

    @pytest.mark.parametrize(
        "query",
        [
            "who is the president",
            "WHAT time is it",
            "WHERE did he go",
            "WHEN will this end",
            "WHY is the sky blue",
            "HOW do I reset my password",
        ],
    )
    def test_starts_with_question_word_case_insensitive(self, query: str) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.QUESTION)
        assert should_research(query, config) is True

    @pytest.mark.parametrize(
        "query",
        [
            "Do this now.",
            "Please summarize this document.",
            "Run the analysis.",
            "Generate a report.",
        ],
    )
    def test_imperative_sentences_are_false(self, query: str) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.QUESTION)
        assert should_research(query, config) is False

    def test_empty_query_is_false(self) -> None:
        config = ResearchConfig(trigger=ResearchTrigger.QUESTION)
        assert should_research("", config) is False


# ── run_research tests ────────────────────────────────────────────────


@pytest.mark.asyncio
class TestRunResearch:
    """Tests for the run_research mini agent loop."""

    async def test_returns_findings_after_sentinel(self) -> None:
        """Provider returns sentinel immediately; findings text is extracted."""
        findings = "The capital of France is Paris."
        response = _make_result(f"[RESEARCH COMPLETE] {findings}")
        provider = MockProvider([response])
        registry = ToolRegistry()

        config = ResearchConfig(trigger=ResearchTrigger.ALWAYS, max_turns=3)
        result = await run_research("What is the capital of France?", config, registry, provider)

        assert result == findings

    async def test_returns_findings_with_multiline_content(self) -> None:
        """Sentinel followed by multiline findings — everything after sentinel returned."""
        findings = "Line 1.\nLine 2.\nLine 3."
        response = _make_result(f"Some preamble.\n[RESEARCH COMPLETE] {findings}")
        provider = MockProvider([response])
        registry = ToolRegistry()

        config = ResearchConfig(trigger=ResearchTrigger.ALWAYS, max_turns=3)
        result = await run_research("Tell me things.", config, registry, provider)

        assert result == findings

    async def test_respects_max_turns_when_no_sentinel(self) -> None:
        """Loop stops after max_turns when sentinel never appears; returns last text."""
        # Provide enough responses for max_turns iterations.
        responses = [_make_result(f"turn {i}") for i in range(5)]
        provider = MockProvider(responses)
        registry = ToolRegistry()

        max_turns = 3
        config = ResearchConfig(trigger=ResearchTrigger.ALWAYS, max_turns=max_turns)
        result = await run_research("some query", config, registry, provider)

        # Should have consumed exactly max_turns calls and returned last content.
        assert provider._call_count == max_turns
        assert result == f"turn {max_turns - 1}"

    async def test_executes_tool_calls_before_sentinel(self) -> None:
        """Tool calls in intermediate turns are executed; sentinel found on final turn."""
        tool_call = ToolCall(id="tc-1", name="mock_tool", arguments={"x": 1})
        intermediate = _make_result("Calling a tool.", tool_calls=[tool_call])
        final = _make_result("[RESEARCH COMPLETE] Done after tool.")

        provider = MockProvider([intermediate, final])

        registry = ToolRegistry()
        # Register a simple mock tool.
        executed: list[dict] = []

        from sage.tools.decorator import tool as tool_decorator

        @tool_decorator
        def mock_tool(x: int) -> str:
            """A mock tool."""
            executed.append({"x": x})
            return "tool output"

        registry.register(mock_tool)

        config = ResearchConfig(trigger=ResearchTrigger.ALWAYS, max_turns=5)
        result = await run_research("query", config, registry, provider)

        assert result == "Done after tool."
        assert executed == [{"x": 1}]
        assert provider._call_count == 2

    async def test_sentinel_at_start_of_content(self) -> None:
        """Sentinel at the very beginning returns empty string after it."""
        response = _make_result("[RESEARCH COMPLETE]")
        provider = MockProvider([response])
        registry = ToolRegistry()

        config = ResearchConfig(trigger=ResearchTrigger.ALWAYS, max_turns=3)
        result = await run_research("q", config, registry, provider)

        assert result == ""

    async def test_no_sentinel_runs_until_max_turns(self) -> None:
        """Without sentinel the loop runs all max_turns, returning the last response text."""
        max_turns = 5
        responses = [_make_result(f"response {i}") for i in range(max_turns)]
        provider = MockProvider(responses)
        registry = ToolRegistry()

        config = ResearchConfig(trigger=ResearchTrigger.ALWAYS, max_turns=max_turns)
        result = await run_research("query", config, registry, provider)

        # All max_turns calls made; last response returned.
        assert provider._call_count == max_turns
        assert result == f"response {max_turns - 1}"

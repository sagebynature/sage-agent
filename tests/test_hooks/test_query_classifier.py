"""Tests for rule-based query classifier hook — TDD, written before implementation."""

from __future__ import annotations

from typing import Any


from sage.hooks.base import HookEvent
from sage.hooks.builtin.query_classifier import (
    ClassificationRule,
    QueryClassifier,
    make_query_classifier,
)


class TestQueryClassifierClassify:
    """Unit tests for QueryClassifier.classify()."""

    def test_keyword_match(self) -> None:
        """A rule with matching keyword routes to the correct target model."""
        rule = ClassificationRule(
            keywords=["code"],
            patterns=[],
            priority=1,
            target_model="gpt-4o",
        )
        qc = QueryClassifier(rules=[rule])
        assert qc.classify("write some code") == "gpt-4o"

    def test_case_insensitive_keyword(self) -> None:
        """Keyword matching is case-insensitive."""
        rule = ClassificationRule(
            keywords=["code"],
            patterns=[],
            priority=1,
            target_model="gpt-4o",
        )
        qc = QueryClassifier(rules=[rule])
        assert qc.classify("write SOME CODE") == "gpt-4o"

    def test_pattern_match(self) -> None:
        """A rule with a regex pattern routes to the correct target model."""
        rule = ClassificationRule(
            keywords=[],
            patterns=[r"\d{4}"],
            priority=1,
            target_model="claude-3",
        )
        qc = QueryClassifier(rules=[rule])
        assert qc.classify("year 2025") == "claude-3"

    def test_priority_ordering_higher_wins(self) -> None:
        """When both rules could match, higher priority rule wins."""
        low_rule = ClassificationRule(
            keywords=["simple"],
            patterns=[],
            priority=1,
            target_model="gpt-4o-mini",
        )
        high_rule = ClassificationRule(
            keywords=["simple", "code"],
            patterns=[],
            priority=10,
            target_model="gpt-4o",
        )
        qc = QueryClassifier(rules=[low_rule, high_rule])
        result = qc.classify("write simple code")
        assert result == "gpt-4o"

    def test_no_match_returns_none(self) -> None:
        """When no rule matches, classify returns None."""
        rule = ClassificationRule(
            keywords=["code"],
            patterns=[],
            priority=1,
            target_model="gpt-4o",
        )
        qc = QueryClassifier(rules=[rule])
        assert qc.classify("hello") is None

    def test_multiple_keywords_any_matches(self) -> None:
        """A rule matches when any of its keywords is found in the query."""
        rule = ClassificationRule(
            keywords=["python", "javascript", "rust"],
            patterns=[],
            priority=1,
            target_model="coding-model",
        )
        qc = QueryClassifier(rules=[rule])
        assert qc.classify("help me with javascript") == "coding-model"
        assert qc.classify("write rust code") == "coding-model"

    def test_no_rules_returns_none(self) -> None:
        """A classifier with no rules always returns None."""
        qc = QueryClassifier(rules=[])
        assert qc.classify("anything at all") is None

    def test_pattern_case_insensitive(self) -> None:
        """Regex patterns compiled with IGNORECASE flag."""
        rule = ClassificationRule(
            keywords=[],
            patterns=[r"urgent"],
            priority=1,
            target_model="fast-model",
        )
        qc = QueryClassifier(rules=[rule])
        assert qc.classify("This is URGENT") == "fast-model"

    def test_priority_lower_rule_wins_when_query_only_matches_it(self) -> None:
        """Lower priority rule wins when higher priority rule doesn't match."""
        low_rule = ClassificationRule(
            keywords=["weather"],
            patterns=[],
            priority=1,
            target_model="light-model",
        )
        high_rule = ClassificationRule(
            keywords=["code"],
            patterns=[],
            priority=10,
            target_model="heavy-model",
        )
        qc = QueryClassifier(rules=[low_rule, high_rule])
        result = qc.classify("what is the weather today")
        assert result == "light-model"

    def test_keyword_substring_match(self) -> None:
        """Keywords match as substrings, not whole words."""
        rule = ClassificationRule(
            keywords=["cod"],
            patterns=[],
            priority=1,
            target_model="gpt-4o",
        )
        qc = QueryClassifier(rules=[rule])
        assert qc.classify("write some code") == "gpt-4o"

    def test_empty_query_no_match(self) -> None:
        """An empty query matches nothing."""
        rule = ClassificationRule(
            keywords=["code"],
            patterns=[],
            priority=1,
            target_model="gpt-4o",
        )
        qc = QueryClassifier(rules=[rule])
        assert qc.classify("") is None


class TestMakeQueryClassifier:
    """Integration tests for the make_query_classifier factory."""

    def test_make_classifier_hook_callable(self) -> None:
        """make_query_classifier returns a callable."""
        rule = ClassificationRule(
            keywords=["code"],
            patterns=[],
            priority=1,
            target_model="gpt-4o",
        )
        hook = make_query_classifier(rules=[rule])
        assert callable(hook)

    async def test_hook_routes_model_dict_messages(self) -> None:
        """Hook modifies data['model'] when a rule matches (dict messages)."""
        rule = ClassificationRule(
            keywords=["code"],
            patterns=[],
            priority=1,
            target_model="gpt-4o",
        )
        hook = make_query_classifier(rules=[rule])
        data: dict[str, Any] = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": "write some code for me"},
            ],
        }
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result is not None
        assert result["model"] == "gpt-4o"

    async def test_hook_no_match_returns_none(self) -> None:
        """Hook returns None when no rule matches."""
        rule = ClassificationRule(
            keywords=["code"],
            patterns=[],
            priority=1,
            target_model="gpt-4o",
        )
        hook = make_query_classifier(rules=[rule])
        data: dict[str, Any] = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": "what is the weather today"},
            ],
        }
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result is None

    async def test_hook_ignores_non_pre_llm_call_event(self) -> None:
        """Hook is a no-op for events other than PRE_LLM_CALL."""
        rule = ClassificationRule(
            keywords=["code"],
            patterns=[],
            priority=1,
            target_model="gpt-4o",
        )
        hook = make_query_classifier(rules=[rule])
        data: dict[str, Any] = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": "write some code"},
            ],
        }
        result = await hook(HookEvent.POST_LLM_CALL, data)
        assert result is None

    async def test_hook_no_user_message_returns_none(self) -> None:
        """Hook returns None when there are no user messages."""
        rule = ClassificationRule(
            keywords=["code"],
            patterns=[],
            priority=1,
            target_model="gpt-4o",
        )
        hook = make_query_classifier(rules=[rule])
        data: dict[str, Any] = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "assistant", "content": "How can I help?"},
            ],
        }
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result is None

    async def test_hook_uses_latest_user_message(self) -> None:
        """Hook uses the last user message in the conversation."""
        rule = ClassificationRule(
            keywords=["code"],
            patterns=[],
            priority=1,
            target_model="gpt-4o",
        )
        hook = make_query_classifier(rules=[rule])
        data: dict[str, Any] = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": "hello there"},
                {"role": "assistant", "content": "Hi! How can I help?"},
                {"role": "user", "content": "write some code for me"},
            ],
        }
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result is not None
        assert result["model"] == "gpt-4o"

    async def test_hook_empty_messages_returns_none(self) -> None:
        """Hook returns None when messages list is empty."""
        rule = ClassificationRule(
            keywords=["code"],
            patterns=[],
            priority=1,
            target_model="gpt-4o",
        )
        hook = make_query_classifier(rules=[rule])
        data: dict[str, Any] = {
            "model": "gpt-3.5-turbo",
            "messages": [],
        }
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result is None

    async def test_hook_missing_messages_key_returns_none(self) -> None:
        """Hook returns None when 'messages' key is absent from data."""
        rule = ClassificationRule(
            keywords=["code"],
            patterns=[],
            priority=1,
            target_model="gpt-4o",
        )
        hook = make_query_classifier(rules=[rule])
        data: dict[str, Any] = {"model": "gpt-3.5-turbo"}
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result is None

"""Tests for TokenBudget."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from sage.context.token_budget import TokenBudget
from sage.models import Message


def _msg(role: str, content: str) -> Message:
    return Message(role=role, content=content)


class TestTokenBudget:
    def test_available_tokens(self) -> None:
        with patch("sage.context.token_budget.litellm") as mock_litellm:
            mock_litellm.get_max_tokens.return_value = 128000
            budget = TokenBudget(model="gpt-4o", reserve_tokens=4096)

        assert budget.available_tokens == 128000 - 4096

    def test_count_messages(self) -> None:
        with patch("sage.context.token_budget.litellm") as mock_litellm:
            mock_litellm.get_max_tokens.return_value = 128000
            mock_litellm.token_counter.return_value = 500
            budget = TokenBudget(model="gpt-4o")

            msgs = [_msg("user", "hello"), _msg("assistant", "hi")]
            count = budget.count_messages(msgs)
            assert count == 500

    def test_should_compact_below_threshold(self) -> None:
        with patch("sage.context.token_budget.litellm") as mock_litellm:
            mock_litellm.get_max_tokens.return_value = 100000
            budget = TokenBudget(model="gpt-4o", compaction_threshold=0.75, reserve_tokens=0)

        msgs = [_msg("user", "hello")]
        with patch.object(budget, "count_messages", return_value=50000):
            assert budget.should_compact(msgs) is False

    def test_should_compact_above_threshold(self) -> None:
        with patch("sage.context.token_budget.litellm") as mock_litellm:
            mock_litellm.get_max_tokens.return_value = 100000
            budget = TokenBudget(model="gpt-4o", compaction_threshold=0.75, reserve_tokens=0)

        msgs = [_msg("user", "hello")]
        with patch.object(budget, "count_messages", return_value=80000):
            assert budget.should_compact(msgs) is True

    def test_usage_report(self) -> None:
        with patch("sage.context.token_budget.litellm") as mock_litellm:
            mock_litellm.get_max_tokens.return_value = 100000
            budget = TokenBudget(model="gpt-4o", compaction_threshold=0.75, reserve_tokens=4096)

        msgs = [_msg("user", "hello")]
        with patch.object(budget, "count_messages", return_value=50000):
            report = budget.usage_report(msgs)

        assert report["tokens_used"] == 50000
        assert report["tokens_available"] == 100000 - 4096
        assert "utilization_pct" in report
        assert "should_compact" in report


class TestTokenBudgetValidation:
    def test_raises_on_zero_max_tokens(self) -> None:
        with patch("sage.context.token_budget.litellm") as mock_litellm:
            mock_litellm.get_max_tokens.return_value = 0
            with pytest.raises(ValueError, match="max_tokens"):
                TokenBudget(model="unknown-model")

    def test_raises_on_none_max_tokens(self) -> None:
        with patch("sage.context.token_budget.litellm") as mock_litellm:
            mock_litellm.get_max_tokens.return_value = None
            with pytest.raises(ValueError, match="max_tokens"):
                TokenBudget(model="unknown-model")

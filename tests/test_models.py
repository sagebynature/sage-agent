"""Tests for Usage model accumulation operators."""

from __future__ import annotations

import pytest

from sage.models import Usage


class TestUsageAdd:
    def test_add_returns_new_instance(self) -> None:
        a = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        b = Usage(prompt_tokens=20, completion_tokens=10, total_tokens=30)
        result = a + b
        assert result is not a
        assert result is not b

    def test_add_sums_all_fields(self) -> None:
        a = Usage(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cache_read_tokens=3,
            cache_creation_tokens=2,
            reasoning_tokens=1,
            cost=0.001,
        )
        b = Usage(
            prompt_tokens=20,
            completion_tokens=10,
            total_tokens=30,
            cache_read_tokens=7,
            cache_creation_tokens=4,
            reasoning_tokens=3,
            cost=0.002,
        )
        result = a + b
        assert result.prompt_tokens == 30
        assert result.completion_tokens == 15
        assert result.total_tokens == 45
        assert result.cache_read_tokens == 10
        assert result.cache_creation_tokens == 6
        assert result.reasoning_tokens == 4
        assert result.cost == pytest.approx(0.003)

    def test_add_with_defaults(self) -> None:
        a = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        b = Usage()
        result = a + b
        assert result.prompt_tokens == 10
        assert result.cache_read_tokens == 0
        assert result.cost == 0.0


class TestUsageIadd:
    def test_iadd_mutates_in_place(self) -> None:
        a = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost=0.001)
        original_id = id(a)
        b = Usage(prompt_tokens=20, completion_tokens=10, total_tokens=30, cost=0.002)
        a += b
        assert id(a) == original_id
        assert a.prompt_tokens == 30
        assert a.completion_tokens == 15
        assert a.total_tokens == 45
        assert a.cost == pytest.approx(0.003)

    def test_iadd_accumulates_cache_fields(self) -> None:
        a = Usage(cache_read_tokens=5, cache_creation_tokens=2, reasoning_tokens=1)
        b = Usage(cache_read_tokens=10, cache_creation_tokens=3, reasoning_tokens=4)
        a += b
        assert a.cache_read_tokens == 15
        assert a.cache_creation_tokens == 5
        assert a.reasoning_tokens == 5

    def test_iadd_multiple_accumulations(self) -> None:
        total = Usage()
        for i in range(5):
            total += Usage(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost=0.01,
            )
        assert total.prompt_tokens == 500
        assert total.completion_tokens == 250
        assert total.total_tokens == 750
        assert total.cost == pytest.approx(0.05)


class TestUsageBackwardCompatibility:
    def test_default_values(self) -> None:
        usage = Usage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0
        assert usage.cache_read_tokens == 0
        assert usage.cache_creation_tokens == 0
        assert usage.reasoning_tokens == 0
        assert usage.cost == 0.0

    def test_original_fields_only(self) -> None:
        usage = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 5
        assert usage.total_tokens == 15
        assert usage.cache_read_tokens == 0
        assert usage.cost == 0.0

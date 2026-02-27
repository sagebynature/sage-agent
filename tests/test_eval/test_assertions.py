"""Tests for sage.eval.assertions — all assertion types except llm_judge and json_schema."""

from __future__ import annotations
from sage.eval.assertions import (
    AssertionResult,
    ContainsAssertion,
    CostUnderAssertion,
    ExactMatchAssertion,
    NoToolCallsAssertion,
    NotContainsAssertion,
    PythonAssertion,
    RegexAssertion,
    ToolCallsAssertion,
    TurnsUnderAssertion,
    run_assertion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run(assertion, output="hello world", tool_calls=None, cost=0.0, turns=0):
    return await run_assertion(
        assertion=assertion,
        output=output,
        tool_calls_made=tool_calls or [],
        cost=cost,
        turns=turns,
    )


# ---------------------------------------------------------------------------
# ExactMatchAssertion
# ---------------------------------------------------------------------------


async def test_exact_match_pass() -> None:
    a = ExactMatchAssertion(type="exact_match", value="hello world")
    result = await _run(a, output="hello world")
    assert result.passed is True
    assert result.score == 1.0


async def test_exact_match_fail() -> None:
    a = ExactMatchAssertion(type="exact_match", value="hello")
    result = await _run(a, output="hello world")
    assert result.passed is False
    assert result.score == 0.0
    assert "hello" in result.message


# ---------------------------------------------------------------------------
# ContainsAssertion
# ---------------------------------------------------------------------------


async def test_contains_pass() -> None:
    a = ContainsAssertion(type="contains", value="world")
    result = await _run(a, output="hello world")
    assert result.passed is True


async def test_contains_fail() -> None:
    a = ContainsAssertion(type="contains", value="foobar")
    result = await _run(a, output="hello world")
    assert result.passed is False
    assert result.score == 0.0


# ---------------------------------------------------------------------------
# NotContainsAssertion
# ---------------------------------------------------------------------------


async def test_not_contains_pass() -> None:
    a = NotContainsAssertion(type="not_contains", value="error")
    result = await _run(a, output="everything is fine")
    assert result.passed is True


async def test_not_contains_fail() -> None:
    a = NotContainsAssertion(type="not_contains", value="error")
    result = await _run(a, output="there was an error")
    assert result.passed is False


# ---------------------------------------------------------------------------
# RegexAssertion
# ---------------------------------------------------------------------------


async def test_regex_pass() -> None:
    a = RegexAssertion(type="regex", pattern=r"\d{4}")
    result = await _run(a, output="The year is 2024")
    assert result.passed is True


async def test_regex_fail() -> None:
    a = RegexAssertion(type="regex", pattern=r"\d{4}")
    result = await _run(a, output="No numbers here")
    assert result.passed is False


# ---------------------------------------------------------------------------
# PythonAssertion
# ---------------------------------------------------------------------------


async def test_python_pass() -> None:
    code = "result = 1.0 if 'hello' in output else 0.0"
    a = PythonAssertion(type="python", code=code)
    result = await _run(a, output="say hello!")
    assert result.passed is True
    assert result.score == 1.0


async def test_python_fail() -> None:
    code = "result = 1.0 if 'hello' in output else 0.0"
    a = PythonAssertion(type="python", code=code)
    result = await _run(a, output="goodbye")
    assert result.passed is False
    assert result.score == 0.0


async def test_python_partial_score() -> None:
    code = "result = 0.7"
    a = PythonAssertion(type="python", code=code)
    result = await _run(a, output="anything")
    assert result.passed is True  # 0.7 >= 0.5
    assert abs(result.score - 0.7) < 0.01


async def test_python_raises_exception() -> None:
    code = "raise ValueError('boom')"
    a = PythonAssertion(type="python", code=code)
    result = await _run(a, output="anything")
    assert result.passed is False
    assert "boom" in result.message


async def test_python_score_clamp() -> None:
    """Result is clamped to 0.0–1.0."""
    code = "result = 99.0"
    a = PythonAssertion(type="python", code=code)
    result = await _run(a, output="any")
    assert result.score == 1.0


# ---------------------------------------------------------------------------
# ToolCallsAssertion
# ---------------------------------------------------------------------------


async def test_tool_calls_pass() -> None:
    a = ToolCallsAssertion(type="tool_calls", expected=["shell", "file_read"])
    result = await _run(a, tool_calls=["shell", "file_read", "extra"])
    assert result.passed is True


async def test_tool_calls_fail_missing() -> None:
    a = ToolCallsAssertion(type="tool_calls", expected=["shell", "file_read"])
    result = await _run(a, tool_calls=["shell"])
    assert result.passed is False
    assert "file_read" in result.message


# ---------------------------------------------------------------------------
# NoToolCallsAssertion
# ---------------------------------------------------------------------------


async def test_no_tool_calls_pass() -> None:
    a = NoToolCallsAssertion(type="no_tool_calls", forbidden=["shell"])
    result = await _run(a, tool_calls=["file_read"])
    assert result.passed is True


async def test_no_tool_calls_fail() -> None:
    a = NoToolCallsAssertion(type="no_tool_calls", forbidden=["shell"])
    result = await _run(a, tool_calls=["shell", "file_read"])
    assert result.passed is False
    assert "shell" in result.message


# ---------------------------------------------------------------------------
# CostUnderAssertion
# ---------------------------------------------------------------------------


async def test_cost_under_pass() -> None:
    a = CostUnderAssertion(type="cost_under", max_cost=0.10)
    result = await _run(a, cost=0.05)
    assert result.passed is True


async def test_cost_under_fail() -> None:
    a = CostUnderAssertion(type="cost_under", max_cost=0.01)
    result = await _run(a, cost=0.05)
    assert result.passed is False


# ---------------------------------------------------------------------------
# TurnsUnderAssertion
# ---------------------------------------------------------------------------


async def test_turns_under_pass() -> None:
    a = TurnsUnderAssertion(type="turns_under", max_turns=5)
    result = await _run(a, turns=3)
    assert result.passed is True


async def test_turns_under_fail() -> None:
    a = TurnsUnderAssertion(type="turns_under", max_turns=5)
    result = await _run(a, turns=5)
    assert result.passed is False


# ---------------------------------------------------------------------------
# AssertionResult model
# ---------------------------------------------------------------------------


def test_assertion_result_model() -> None:
    r = AssertionResult(type="contains", passed=True, score=1.0, message="ok")
    assert r.type == "contains"
    assert r.passed is True
    assert r.score == 1.0


def test_assertion_result_default_message() -> None:
    r = AssertionResult(type="regex", passed=False, score=0.0)
    assert r.message == ""

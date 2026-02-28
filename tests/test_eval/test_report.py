"""Tests for sage.eval.report — format_run_text, format_run_json, format_comparison_text."""

from __future__ import annotations
import json

from sage.eval.assertions import AssertionResult
from sage.eval.report import format_comparison_text, format_run_json, format_run_text
from sage.eval.runner import CaseResult, EvalRunResult
from sage.models import Usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(
    run_id: str = "run-123",
    suite_name: str = "my-suite",
    model: str = "gpt-4o",
    pass_rate: float = 0.75,
    avg_score: float = 0.8,
    pass_count: int = 3,
    fail_count: int = 1,
) -> EvalRunResult:
    results = []
    for i in range(pass_count):
        results.append(
            CaseResult(
                case_id=f"tc-pass-{i}",
                passed=True,
                score=1.0,
                output="great answer",
                assertion_results=[
                    AssertionResult(type="contains", passed=True, score=1.0),
                ],
                tool_calls_made=[],
                latency_ms=200,
                tokens=100,
                cost=0.002,
            )
        )
    for i in range(fail_count):
        results.append(
            CaseResult(
                case_id=f"tc-fail-{i}",
                passed=False,
                score=0.0,
                output="wrong answer",
                assertion_results=[
                    AssertionResult(
                        type="exact_match",
                        passed=False,
                        score=0.0,
                        message="Expected exact: 'correct'",
                    ),
                ],
                tool_calls_made=[],
                latency_ms=300,
                tokens=150,
                cost=0.003,
            )
        )

    return EvalRunResult(
        run_id=run_id,
        suite_name=suite_name,
        model=model,
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:01:00+00:00",
        pass_rate=pass_rate,
        avg_score=avg_score,
        total_cost=pass_count * 0.002 + fail_count * 0.003,
        total_tokens=pass_count * 100 + fail_count * 150,
        results=results,
    )


# ---------------------------------------------------------------------------
# format_run_text
# ---------------------------------------------------------------------------


def test_format_run_text_contains_suite_name() -> None:
    run = _make_run()
    text = format_run_text(run)
    assert "my-suite" in text


def test_format_run_text_contains_model() -> None:
    run = _make_run()
    text = format_run_text(run)
    assert "gpt-4o" in text


def test_format_run_text_contains_pass_rate() -> None:
    run = _make_run(pass_rate=0.75)
    text = format_run_text(run)
    assert "75.0%" in text


def test_format_run_text_contains_run_id() -> None:
    run = _make_run(run_id="run-abc-123")
    text = format_run_text(run)
    assert "run-abc-123" in text


def test_format_run_text_pass_fail_labels() -> None:
    run = _make_run(pass_count=2, fail_count=1)
    text = format_run_text(run)
    assert "PASS" in text
    assert "FAIL" in text


def test_format_run_text_assertion_results() -> None:
    run = _make_run()
    text = format_run_text(run)
    # Should include assertion type markers
    assert "contains" in text or "exact_match" in text


def test_format_run_text_error_shown() -> None:
    run = _make_run(pass_count=0, fail_count=0)
    # Add a case with an error
    error_case = CaseResult(
        case_id="tc-err",
        passed=False,
        score=0.0,
        output="",
        assertion_results=[],
        tool_calls_made=[],
        latency_ms=0,
        tokens=0,
        cost=0.0,
        error="Timeout after 60s",
    )
    run.results.append(error_case)
    text = format_run_text(run)
    assert "Timeout" in text


# ---------------------------------------------------------------------------
# format_run_json
# ---------------------------------------------------------------------------


def test_format_run_json_is_valid_json() -> None:
    run = _make_run()
    json_str = format_run_json(run)
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)


def test_format_run_json_contains_run_id() -> None:
    run = _make_run(run_id="run-json-test")
    json_str = format_run_json(run)
    parsed = json.loads(json_str)
    assert parsed["run_id"] == "run-json-test"


def test_format_run_json_contains_results() -> None:
    run = _make_run(pass_count=2, fail_count=1)
    json_str = format_run_json(run)
    parsed = json.loads(json_str)
    assert "results" in parsed
    assert len(parsed["results"]) == 3


def test_format_run_json_contains_pass_rate() -> None:
    run = _make_run(pass_rate=0.5)
    json_str = format_run_json(run)
    parsed = json.loads(json_str)
    assert parsed["pass_rate"] == 0.5


# ---------------------------------------------------------------------------
# format_comparison_text
# ---------------------------------------------------------------------------


def test_format_comparison_text_normal() -> None:
    comparison = {
        "run_1": {
            "id": "r1",
            "model": "gpt-4o",
            "suite_name": "suite",
            "started_at": "2026-01-01T00:00:00+00:00",
            "pass_rate": 0.5,
            "avg_score": 0.6,
            "total_cost": 0.01,
            "total_tokens": 500,
        },
        "run_2": {
            "id": "r2",
            "model": "gpt-4o-mini",
            "suite_name": "suite",
            "started_at": "2026-01-02T00:00:00+00:00",
            "pass_rate": 1.0,
            "avg_score": 0.9,
            "total_cost": 0.005,
            "total_tokens": 400,
        },
        "delta": {
            "pass_rate": 0.5,
            "avg_score": 0.3,
            "total_cost": -0.005,
            "total_tokens": -100,
        },
    }
    text = format_comparison_text(comparison)
    assert "Run Comparison" in text
    assert "gpt-4o" in text
    assert "gpt-4o-mini" in text
    assert "r1" in text
    assert "r2" in text


def test_format_comparison_text_error() -> None:
    comparison = {"error": "Run(s) not found: missing-id"}
    text = format_comparison_text(comparison)
    assert "error" in text.lower()
    assert "missing-id" in text


def test_format_run_text_token_breakdown() -> None:
    usage = Usage(
        prompt_tokens=800,
        completion_tokens=200,
        total_tokens=1000,
        cache_read_tokens=300,
        cache_creation_tokens=50,
        reasoning_tokens=0,
        cost=0.004,
    )
    case = CaseResult(
        case_id="tc-tokens",
        passed=True,
        score=1.0,
        output="answer",
        assertion_results=[
            AssertionResult(type="contains", passed=True, score=1.0),
        ],
        tool_calls_made=[],
        latency_ms=500,
        tokens=1000,
        cost=0.004,
        usage=usage,
    )
    run = EvalRunResult(
        run_id="run-tok",
        suite_name="token-suite",
        model="gpt-4o",
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:01:00+00:00",
        pass_rate=1.0,
        avg_score=1.0,
        total_cost=0.004,
        total_tokens=1000,
        total_usage=usage,
        results=[case],
    )
    text = format_run_text(run)
    # Summary-level token breakdown
    assert "Input:" in text
    assert "Output:" in text
    assert "800" in text
    assert "200" in text
    assert "Cache read:" in text
    assert "Cache write:" in text
    # Per-case token line
    assert "in=800" in text
    assert "out=200" in text
    assert "cache_read=300" in text
    assert "cache_write=50" in text


def test_format_run_json_includes_usage() -> None:
    usage = Usage(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost=0.001,
    )
    case = CaseResult(
        case_id="tc-1",
        passed=True,
        score=1.0,
        output="ok",
        assertion_results=[],
        tool_calls_made=[],
        latency_ms=100,
        tokens=150,
        cost=0.001,
        usage=usage,
    )
    run = EvalRunResult(
        run_id="run-json-usage",
        suite_name="suite",
        model="gpt-4o",
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:01:00+00:00",
        pass_rate=1.0,
        avg_score=1.0,
        total_cost=0.001,
        total_tokens=150,
        total_usage=usage,
        results=[case],
    )
    parsed = json.loads(format_run_json(run))
    assert parsed["total_usage"]["prompt_tokens"] == 100
    assert parsed["total_usage"]["completion_tokens"] == 50
    assert parsed["results"][0]["usage"]["prompt_tokens"] == 100


def test_format_comparison_text_delta_shown() -> None:
    comparison = {
        "run_1": {
            "id": "r1",
            "model": "gpt-4o",
            "suite_name": "s",
            "started_at": "",
            "pass_rate": 0.4,
            "avg_score": 0.5,
            "total_cost": 0.02,
            "total_tokens": 200,
        },
        "run_2": {
            "id": "r2",
            "model": "gpt-4o",
            "suite_name": "s",
            "started_at": "",
            "pass_rate": 0.8,
            "avg_score": 0.9,
            "total_cost": 0.01,
            "total_tokens": 100,
        },
        "delta": {
            "pass_rate": 0.4,
            "avg_score": 0.4,
            "total_cost": -0.01,
            "total_tokens": -100,
        },
    }
    text = format_comparison_text(comparison)
    # Should show + prefix for positive delta
    assert "+" in text or "40.0%" in text

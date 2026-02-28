"""Tests for sage.eval.history — EvalHistory SQLite persistence."""

from __future__ import annotations
from pathlib import Path
from sage.eval.assertions import AssertionResult
from sage.eval.history import EvalHistory
from sage.eval.runner import CaseResult, EvalRunResult
from sage.models import Usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(
    run_id: str = "run-abc",
    suite_name: str = "test-suite",
    model: str = "gpt-4o",
    pass_rate: float = 1.0,
    avg_score: float = 0.9,
) -> EvalRunResult:
    case = CaseResult(
        case_id="tc-1",
        passed=True,
        score=0.9,
        output="hello",
        assertion_results=[
            AssertionResult(type="contains", passed=True, score=1.0),
        ],
        tool_calls_made=[],
        latency_ms=100,
        tokens=50,
        cost=0.001,
    )
    return EvalRunResult(
        run_id=run_id,
        suite_name=suite_name,
        model=model,
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:01:00+00:00",
        pass_rate=pass_rate,
        avg_score=avg_score,
        total_cost=0.001,
        total_tokens=50,
        results=[case],
    )


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------


async def test_init_db_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "eval.db"
    history = EvalHistory(db_path=db_path)
    await history.init_db()
    assert db_path.exists()


async def test_init_db_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "eval.db"
    history = EvalHistory(db_path=db_path)
    await history.init_db()
    await history.init_db()  # Should not raise
    assert db_path.exists()


# ---------------------------------------------------------------------------
# save_run / list_runs
# ---------------------------------------------------------------------------


async def test_save_and_list_run(tmp_path: Path) -> None:
    history = EvalHistory(db_path=tmp_path / "eval.db")
    await history.init_db()

    run = _make_run(run_id="run-001")
    await history.save_run(run)

    runs = await history.list_runs()
    assert len(runs) == 1
    assert runs[0]["id"] == "run-001"
    assert runs[0]["suite_name"] == "test-suite"
    assert runs[0]["model"] == "gpt-4o"


async def test_list_runs_empty(tmp_path: Path) -> None:
    history = EvalHistory(db_path=tmp_path / "eval.db")
    await history.init_db()
    runs = await history.list_runs()
    assert runs == []


async def test_list_runs_filter_by_suite(tmp_path: Path) -> None:
    history = EvalHistory(db_path=tmp_path / "eval.db")
    await history.init_db()

    await history.save_run(_make_run(run_id="r1", suite_name="suite-a"))
    await history.save_run(_make_run(run_id="r2", suite_name="suite-b"))
    await history.save_run(_make_run(run_id="r3", suite_name="suite-a"))

    suite_a_runs = await history.list_runs(suite_name="suite-a")
    assert len(suite_a_runs) == 2
    for r in suite_a_runs:
        assert r["suite_name"] == "suite-a"


async def test_list_runs_last_limit(tmp_path: Path) -> None:
    history = EvalHistory(db_path=tmp_path / "eval.db")
    await history.init_db()

    for i in range(5):
        await history.save_run(_make_run(run_id=f"run-{i:03d}"))

    runs = await history.list_runs(last=3)
    assert len(runs) == 3


# ---------------------------------------------------------------------------
# get_run
# ---------------------------------------------------------------------------


async def test_get_run_existing(tmp_path: Path) -> None:
    history = EvalHistory(db_path=tmp_path / "eval.db")
    await history.init_db()

    run = _make_run(run_id="run-xyz")
    await history.save_run(run)

    retrieved = await history.get_run("run-xyz")
    assert retrieved is not None
    assert retrieved["id"] == "run-xyz"
    assert "results" in retrieved
    assert len(retrieved["results"]) == 1


async def test_get_run_nonexistent(tmp_path: Path) -> None:
    history = EvalHistory(db_path=tmp_path / "eval.db")
    await history.init_db()
    result = await history.get_run("nonexistent-id")
    assert result is None


async def test_get_run_assertion_results_deserialized(tmp_path: Path) -> None:
    history = EvalHistory(db_path=tmp_path / "eval.db")
    await history.init_db()

    run = _make_run(run_id="run-assert")
    await history.save_run(run)

    retrieved = await history.get_run("run-assert")
    assert retrieved is not None
    case_row = retrieved["results"][0]
    assert isinstance(case_row["assertion_results"], list)
    assert isinstance(case_row["tool_calls_made"], list)


# ---------------------------------------------------------------------------
# compare_runs
# ---------------------------------------------------------------------------


async def test_compare_runs_both_exist(tmp_path: Path) -> None:
    history = EvalHistory(db_path=tmp_path / "eval.db")
    await history.init_db()

    run1 = _make_run(run_id="r1", pass_rate=0.5, avg_score=0.6, model="gpt-4o")
    run2 = _make_run(run_id="r2", pass_rate=1.0, avg_score=0.9, model="gpt-4o-mini")
    await history.save_run(run1)
    await history.save_run(run2)

    comparison = await history.compare_runs("r1", "r2")
    assert "error" not in comparison
    assert comparison["run_1"]["id"] == "r1"
    assert comparison["run_2"]["id"] == "r2"
    assert "delta" in comparison
    # delta.pass_rate should be approximately 0.5
    assert abs(comparison["delta"]["pass_rate"] - 0.5) < 0.001


async def test_compare_runs_missing_run(tmp_path: Path) -> None:
    history = EvalHistory(db_path=tmp_path / "eval.db")
    await history.init_db()

    run1 = _make_run(run_id="r1")
    await history.save_run(run1)

    comparison = await history.compare_runs("r1", "nonexistent")
    assert "error" in comparison
    assert "nonexistent" in comparison["error"]


async def test_compare_runs_both_missing(tmp_path: Path) -> None:
    history = EvalHistory(db_path=tmp_path / "eval.db")
    await history.init_db()

    comparison = await history.compare_runs("x", "y")
    assert "error" in comparison


# ---------------------------------------------------------------------------
# token_usage persistence
# ---------------------------------------------------------------------------


async def test_token_usage_persisted(tmp_path: Path) -> None:
    history = EvalHistory(db_path=tmp_path / "eval.db")
    await history.init_db()

    usage = Usage(
        prompt_tokens=1000,
        completion_tokens=200,
        total_tokens=1200,
        cache_read_tokens=500,
        cache_creation_tokens=100,
        reasoning_tokens=50,
        cost=0.005,
    )
    case = CaseResult(
        case_id="tc-1",
        passed=True,
        score=0.9,
        output="hello",
        assertion_results=[
            AssertionResult(type="contains", passed=True, score=1.0),
        ],
        tool_calls_made=[],
        latency_ms=100,
        tokens=1200,
        cost=0.005,
        usage=usage,
    )
    run = EvalRunResult(
        run_id="run-usage",
        suite_name="test-suite",
        model="gpt-4o",
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:01:00+00:00",
        pass_rate=1.0,
        avg_score=0.9,
        total_cost=0.005,
        total_tokens=1200,
        total_usage=usage,
        results=[case],
    )
    await history.save_run(run)

    retrieved = await history.get_run("run-usage")
    assert retrieved is not None

    # Check run-level token usage
    tu = retrieved["total_token_usage"]
    assert tu["prompt_tokens"] == 1000
    assert tu["completion_tokens"] == 200
    assert tu["cache_read_tokens"] == 500
    assert tu["cache_creation_tokens"] == 100
    assert tu["reasoning_tokens"] == 50

    # Check case-level token usage
    case_tu = retrieved["results"][0]["token_usage"]
    assert case_tu["prompt_tokens"] == 1000
    assert case_tu["completion_tokens"] == 200
    assert case_tu["cache_read_tokens"] == 500

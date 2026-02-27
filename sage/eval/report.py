"""Report generation for eval run results."""

from __future__ import annotations
from typing import Any

from sage.eval.runner import EvalRunResult


def format_run_text(run: EvalRunResult) -> str:
    """Human-readable text report."""
    lines = [
        f"Eval Run: {run.suite_name}",
        f"  Run ID:     {run.run_id}",
        f"  Model:      {run.model}",
        f"  Started:    {run.started_at}",
        f"  Completed:  {run.completed_at}",
        f"  Pass rate:  {run.pass_rate:.1%}  ({sum(1 for r in run.results if r.passed)}/{len(run.results)})",
        f"  Avg score:  {run.avg_score:.3f}",
        f"  Total cost: ${run.total_cost:.4f}",
        f"  Tokens:     {run.total_tokens}",
        "",
        "Case results:",
    ]

    for result in run.results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(
            f"  [{status}] {result.case_id}  score={result.score:.3f}  "
            f"latency={result.latency_ms}ms"
        )
        if result.error:
            lines.append(f"         Error: {result.error}")
        for ar in result.assertion_results:
            check = "✓" if ar.passed else "✗"
            msg = f" — {ar.message}" if ar.message else ""
            lines.append(f"         {check} {ar.type}{msg}")

    return "\n".join(lines)


def format_run_json(run: EvalRunResult) -> str:
    """JSON report."""
    return run.model_dump_json(indent=2)


def format_comparison_text(comparison: dict[str, Any]) -> str:
    """Human-readable comparison of two runs."""
    if "error" in comparison:
        return f"Comparison error: {comparison['error']}"

    run1 = comparison.get("run_1", {})
    run2 = comparison.get("run_2", {})
    delta = comparison.get("delta", {})

    def _fmt_delta(val: float | None, fmt: str = ".3f") -> str:
        if val is None:
            return "N/A"
        sign = "+" if val > 0 else ""
        return f"{sign}{val:{fmt}}"

    lines = [
        "Run Comparison",
        "=" * 50,
        f"{'Metric':<20} {'Run 1':>12} {'Run 2':>12} {'Delta':>12}",
        "-" * 50,
        (
            f"{'Pass rate':<20} {run1.get('pass_rate', 0):.1%}   "
            f"{run2.get('pass_rate', 0):>10.1%}   "
            f"{_fmt_delta(delta.get('pass_rate'), '.1%'):>12}"
        ),
        (
            f"{'Avg score':<20} {run1.get('avg_score', 0):>12.3f} "
            f"{run2.get('avg_score', 0):>12.3f} "
            f"{_fmt_delta(delta.get('avg_score')):>12}"
        ),
        (
            f"{'Total cost ($)':<20} {run1.get('total_cost', 0):>12.4f} "
            f"{run2.get('total_cost', 0):>12.4f} "
            f"{_fmt_delta(delta.get('total_cost'), '.4f'):>12}"
        ),
        (
            f"{'Total tokens':<20} {run1.get('total_tokens', 0):>12} "
            f"{run2.get('total_tokens', 0):>12} "
            f"{_fmt_delta(delta.get('total_tokens'), 'd') if delta.get('total_tokens') is not None else 'N/A':>12}"
        ),
        "-" * 50,
        f"Run 1: {run1.get('model', '')} — {run1.get('id', '')}",
        f"Run 2: {run2.get('model', '')} — {run2.get('id', '')}",
    ]
    return "\n".join(lines)

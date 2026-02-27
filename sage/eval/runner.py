"""EvalRunner — runs TestSuite against an agent and returns aggregated results."""

from __future__ import annotations
import asyncio
import logging
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from sage.eval.assertions import AssertionResult, run_assertion
from sage.eval.suite import TestCase, TestSuite

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class CaseResult(BaseModel):
    """Result for a single test case run."""

    case_id: str
    passed: bool
    score: float
    output: str
    assertion_results: list[AssertionResult]
    tool_calls_made: list[str]
    latency_ms: int
    tokens: int
    cost: float
    error: str | None = None


class EvalRunResult(BaseModel):
    """Aggregated results for a full eval suite run."""

    run_id: str
    suite_name: str
    model: str
    started_at: str
    completed_at: str
    pass_rate: float
    avg_score: float
    total_cost: float
    total_tokens: int
    results: list[CaseResult]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class EvalRunner:
    """Runs a TestSuite against an agent and returns aggregated results."""

    def __init__(self, suite: TestSuite, model: str | None = None) -> None:
        self.suite = suite
        self.model: str = model or (suite.settings.models[0] if suite.settings.models else "gpt-4o")

    async def run(self, runs_per_case: int = 1) -> EvalRunResult:
        """Run all test cases and return aggregated results."""
        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()

        case_results: list[CaseResult] = []
        for test_case in self.suite.test_cases:
            for _ in range(runs_per_case):
                result = await self._run_case(test_case)
                case_results.append(result)

        completed_at = datetime.now(timezone.utc).isoformat()

        passed_count = sum(1 for r in case_results if r.passed)
        pass_rate = passed_count / len(case_results) if case_results else 0.0
        avg_score = sum(r.score for r in case_results) / len(case_results) if case_results else 0.0
        total_cost = sum(r.cost for r in case_results)
        total_tokens = sum(r.tokens for r in case_results)

        return EvalRunResult(
            run_id=run_id,
            suite_name=self.suite.name,
            model=self.model,
            started_at=started_at,
            completed_at=completed_at,
            pass_rate=pass_rate,
            avg_score=avg_score,
            total_cost=total_cost,
            total_tokens=total_tokens,
            results=case_results,
        )

    async def _run_case(self, test_case: TestCase) -> CaseResult:
        """Run a single test case and return its result."""
        from sage.agent import Agent

        output = ""
        tool_calls_made: list[str] = []
        latency_ms = 0
        tokens = 0
        cost = 0.0
        error: str | None = None

        try:
            agent = Agent.from_config(self.suite.agent)
            # Override model
            agent.model = self.model

            # Set up working directory with context files
            tmp_dir: str | None = None
            if test_case.context_files:
                tmp_dir = tempfile.mkdtemp()
                for file_path in test_case.context_files:
                    src = Path(file_path)
                    if src.exists():
                        shutil.copy2(src, Path(tmp_dir) / src.name)
                    else:
                        logger.warning("Context file not found: %s", file_path)
                if hasattr(agent, "cwd"):
                    agent.cwd = tmp_dir  # type: ignore[assignment]

            # Capture tool calls via a hook on the tool registry
            original_dispatch: Any = None
            if hasattr(agent, "tool_registry") and hasattr(agent.tool_registry, "dispatch"):
                original_dispatch = agent.tool_registry.dispatch

                async def _tracking_dispatch(
                    tool_name: str, args: dict[str, Any], *a: Any, **kw: Any
                ) -> Any:
                    tool_calls_made.append(tool_name)
                    return await original_dispatch(tool_name, args, *a, **kw)

                agent.tool_registry.dispatch = _tracking_dispatch  # type: ignore[method-assign]

            try:
                t0 = time.monotonic()
                output = await asyncio.wait_for(
                    agent.run(test_case.input),
                    timeout=self.suite.settings.timeout,
                )
                latency_ms = int((time.monotonic() - t0) * 1000)

                # Try to extract token / cost info from agent internals
                if hasattr(agent, "_token_usage"):
                    tokens = int(agent._token_usage)  # type: ignore[attr-defined]

            finally:
                await agent.close()
                if tmp_dir:
                    shutil.rmtree(tmp_dir, ignore_errors=True)

        except asyncio.TimeoutError:
            error = f"Timeout after {self.suite.settings.timeout}s"
            logger.warning("Case %s timed out", test_case.id)
        except Exception as exc:
            error = str(exc)
            logger.warning("Case %s failed: %s", test_case.id, exc)

        # Run assertions
        assertion_results: list[AssertionResult] = []
        if not error:
            for assertion in test_case.assertions:
                try:
                    result = await run_assertion(
                        assertion=assertion,
                        output=output,
                        tool_calls_made=tool_calls_made,
                        cost=cost,
                        turns=0,  # turns not tracked yet
                        judge_model=self.model,
                        rubric_name=self.suite.rubric,
                    )
                    assertion_results.append(result)
                except Exception as exc:
                    logger.warning("Assertion %s failed with exception: %s", assertion.type, exc)
                    assertion_results.append(
                        AssertionResult(
                            type=assertion.type,
                            passed=False,
                            score=0.0,
                            message=f"Assertion error: {exc}",
                        )
                    )

        # A case passes if all assertions pass (or there are no assertions)
        all_passed = (
            all(r.passed for r in assertion_results) if assertion_results else error is None
        )
        avg_score = (
            sum(r.score for r in assertion_results) / len(assertion_results)
            if assertion_results
            else (1.0 if error is None else 0.0)
        )

        return CaseResult(
            case_id=test_case.id,
            passed=all_passed and error is None,
            score=avg_score,
            output=output,
            assertion_results=assertion_results,
            tool_calls_made=tool_calls_made,
            latency_ms=latency_ms,
            tokens=tokens,
            cost=cost,
            error=error,
        )

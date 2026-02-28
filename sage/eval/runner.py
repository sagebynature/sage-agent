"""EvalRunner — runs TestSuite against an agent and returns aggregated results."""

from __future__ import annotations
import asyncio
import logging
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from sage.eval.assertions import AssertionResult, run_assertion
from sage.eval.suite import TestCase, TestSuite
from sage.models import Usage

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
    usage: Usage = Field(default_factory=Usage)
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
    total_usage: Usage = Field(default_factory=Usage)
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
                # Run each case in its own asyncio Task to fully isolate
                # cancellation scopes — the MCP library uses anyio, and
                # cancel scopes from one case's cleanup can leak into the
                # next case if they share the same Task.
                result = await asyncio.ensure_future(self._run_case(test_case))
                case_results.append(result)

        completed_at = datetime.now(timezone.utc).isoformat()

        passed_count = sum(1 for r in case_results if r.passed)
        pass_rate = passed_count / len(case_results) if case_results else 0.0
        avg_score = sum(r.score for r in case_results) / len(case_results) if case_results else 0.0
        total_cost = sum(r.cost for r in case_results)
        total_tokens = sum(r.tokens for r in case_results)
        total_usage = Usage()
        for r in case_results:
            total_usage += r.usage

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
            total_usage=total_usage,
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
        usage = Usage()
        error: str | None = None
        agent: Agent | None = None
        tmp_dir: str | None = None
        original_cwd: str | None = None

        # --- Phase 1: run the agent ---
        try:
            agent = Agent.from_config(self.suite.agent)
            # Override model
            agent.model = self.model

            # Always run each case in its own temp directory so that file
            # writes are isolated (especially important when models run in
            # parallel).  Copy any context_files into the temp dir preserving
            # relative directory structure so paths in the test input resolve.
            tmp_dir = tempfile.mkdtemp()
            original_cwd = os.getcwd()
            suite_dir = Path(self.suite.suite_dir)
            for file_path in test_case.context_files:
                src = Path(file_path)
                if src.exists():
                    try:
                        rel = src.relative_to(suite_dir)
                    except ValueError:
                        rel = Path(src.name)
                    dest = Path(tmp_dir) / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                else:
                    logger.warning("Context file not found: %s", file_path)

            os.chdir(tmp_dir)

            # Capture tool calls via a hook on the tool registry
            original_execute: Any = None
            if hasattr(agent, "tool_registry") and hasattr(agent.tool_registry, "execute"):
                original_execute = agent.tool_registry.execute

                async def _tracking_execute(
                    name: str,
                    arguments: dict[str, Any],
                ) -> str:
                    tool_calls_made.append(name)
                    return await original_execute(name, arguments)

                agent.tool_registry.execute = _tracking_execute  # type: ignore[method-assign]

            t0 = time.monotonic()
            output = await asyncio.wait_for(
                agent.run(test_case.input),
                timeout=self.suite.settings.timeout,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)

            # Try to extract token / cost info from agent internals
            if hasattr(agent, "cumulative_usage"):
                cu = agent.cumulative_usage
                tokens = cu.total_tokens
                cost = cu.cost
                usage = cu.model_copy()
            elif hasattr(agent, "_token_usage"):
                tokens = int(agent._token_usage)  # type: ignore[attr-defined]

        except asyncio.TimeoutError:
            error = f"Timeout after {self.suite.settings.timeout}s"
            logger.warning("Case %s timed out", test_case.id)
        except asyncio.CancelledError:
            error = f"Cancelled during case {test_case.id}"
            logger.warning("Case %s cancelled", test_case.id)
        except Exception as exc:
            error = str(exc)
            logger.warning("Case %s failed: %s", test_case.id, exc)
        finally:
            # Restore working directory before anything else.
            if original_cwd is not None:
                os.chdir(original_cwd)

        # --- Phase 2: run assertions BEFORE closing the agent ---
        # agent.close() uses anyio internally; its cancel scopes leak across
        # asyncio Task boundaries and cancel unrelated awaits.  By running
        # assertions first, there is nothing left to interfere with.
        assertion_results: list[AssertionResult] = []
        if not error:
            judge_model = self.suite.settings.judge_model or self.model
            for assertion in test_case.assertions:
                try:
                    result = await run_assertion(
                        assertion=assertion,
                        output=output,
                        tool_calls_made=tool_calls_made,
                        cost=cost,
                        turns=0,  # turns not tracked yet
                        judge_model=judge_model,
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

        # --- Phase 3: close agent, then clean up temp dir ---
        if agent is not None:
            try:
                await agent.close()
            except (asyncio.CancelledError, Exception) as exc:
                logger.debug("Agent close error (safe to ignore): %s", exc)
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

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
            usage=usage,
            error=error,
        )

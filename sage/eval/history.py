"""SQLite-backed history store for eval runs."""

from __future__ import annotations
import json
import logging
import uuid
from pathlib import Path

import aiosqlite

from sage.eval.runner import EvalRunResult

logger = logging.getLogger(__name__)

DB_PATH = Path.home() / ".config" / "sage" / "eval_history.db"

_CREATE_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS eval_runs (
    id TEXT PRIMARY KEY,
    suite_name TEXT NOT NULL,
    model TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    pass_rate REAL,
    avg_score REAL,
    total_cost REAL,
    total_tokens INTEGER,
    metadata TEXT DEFAULT '{}'
);
"""

_CREATE_RESULTS_TABLE = """
CREATE TABLE IF NOT EXISTS eval_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES eval_runs(id),
    test_case_id TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    score REAL,
    output TEXT,
    assertion_results TEXT,
    tool_calls_made TEXT,
    latency_ms INTEGER,
    tokens INTEGER,
    cost REAL
);
"""


class EvalHistory:
    """Persists eval run results to a local SQLite database."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    async def init_db(self) -> None:
        """Create tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(_CREATE_RUNS_TABLE)
            await db.execute(_CREATE_RESULTS_TABLE)
            # Migrate: add token_usage columns if they don't exist yet.
            for table, col in [
                ("eval_runs", "total_token_usage"),
                ("eval_results", "token_usage"),
            ]:
                try:
                    await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT '{{}}'")
                except Exception:
                    pass  # column already exists
            await db.commit()

    async def save_run(self, run: EvalRunResult) -> None:
        """Persist a run and its case results."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO eval_runs
                  (id, suite_name, model, started_at, completed_at,
                   pass_rate, avg_score, total_cost, total_tokens, metadata,
                   total_token_usage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.suite_name,
                    run.model,
                    run.started_at,
                    run.completed_at,
                    run.pass_rate,
                    run.avg_score,
                    run.total_cost,
                    run.total_tokens,
                    "{}",
                    run.total_usage.model_dump_json(),
                ),
            )
            for case_result in run.results:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO eval_results
                      (id, run_id, test_case_id, passed, score, output,
                       assertion_results, tool_calls_made, latency_ms, tokens, cost,
                       token_usage)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        run.run_id,
                        case_result.case_id,
                        case_result.passed,
                        case_result.score,
                        case_result.output,
                        json.dumps([r.model_dump() for r in case_result.assertion_results]),
                        json.dumps(case_result.tool_calls_made),
                        case_result.latency_ms,
                        case_result.tokens,
                        case_result.cost,
                        case_result.usage.model_dump_json(),
                    ),
                )
            await db.commit()

    async def list_runs(self, suite_name: str | None = None, last: int = 20) -> list[dict]:
        """Return run summaries (id, suite_name, model, started_at, pass_rate, avg_score)."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            if suite_name is not None:
                cursor = await db.execute(
                    """
                    SELECT id, suite_name, model, started_at, pass_rate, avg_score
                    FROM eval_runs
                    WHERE suite_name = ?
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (suite_name, last),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT id, suite_name, model, started_at, pass_rate, avg_score
                    FROM eval_runs
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (last,),
                )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_run(self, run_id: str) -> dict | None:
        """Return full run data including case results."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute("SELECT * FROM eval_runs WHERE id = ?", (run_id,))
            run_row = await cursor.fetchone()
            if run_row is None:
                return None

            run_data = dict(run_row)
            # Deserialize token usage
            try:
                run_data["total_token_usage"] = json.loads(
                    run_data.get("total_token_usage") or "{}"
                )
            except json.JSONDecodeError:
                run_data["total_token_usage"] = {}

            cursor = await db.execute("SELECT * FROM eval_results WHERE run_id = ?", (run_id,))
            result_rows = await cursor.fetchall()
            results = []
            for row in result_rows:
                row_dict = dict(row)
                # Deserialize JSON fields
                try:
                    row_dict["assertion_results"] = json.loads(
                        row_dict.get("assertion_results") or "[]"
                    )
                except json.JSONDecodeError:
                    row_dict["assertion_results"] = []
                try:
                    row_dict["tool_calls_made"] = json.loads(
                        row_dict.get("tool_calls_made") or "[]"
                    )
                except json.JSONDecodeError:
                    row_dict["tool_calls_made"] = []
                try:
                    row_dict["token_usage"] = json.loads(row_dict.get("token_usage") or "{}")
                except json.JSONDecodeError:
                    row_dict["token_usage"] = {}
                results.append(row_dict)

            run_data["results"] = results
            return run_data

    async def compare_runs(self, run_id_1: str, run_id_2: str) -> dict:
        """Return side-by-side comparison of two runs."""
        run1 = await self.get_run(run_id_1)
        run2 = await self.get_run(run_id_2)

        if run1 is None or run2 is None:
            missing = []
            if run1 is None:
                missing.append(run_id_1)
            if run2 is None:
                missing.append(run_id_2)
            return {"error": f"Run(s) not found: {', '.join(missing)}"}

        def _delta(a: float | None, b: float | None) -> float | None:
            if a is None or b is None:
                return None
            return b - a

        return {
            "run_1": {
                "id": run1["id"],
                "suite_name": run1["suite_name"],
                "model": run1["model"],
                "started_at": run1["started_at"],
                "pass_rate": run1["pass_rate"],
                "avg_score": run1["avg_score"],
                "total_cost": run1["total_cost"],
                "total_tokens": run1["total_tokens"],
            },
            "run_2": {
                "id": run2["id"],
                "suite_name": run2["suite_name"],
                "model": run2["model"],
                "started_at": run2["started_at"],
                "pass_rate": run2["pass_rate"],
                "avg_score": run2["avg_score"],
                "total_cost": run2["total_cost"],
                "total_tokens": run2["total_tokens"],
            },
            "delta": {
                "pass_rate": _delta(run1.get("pass_rate"), run2.get("pass_rate")),
                "avg_score": _delta(run1.get("avg_score"), run2.get("avg_score")),
                "total_cost": _delta(run1.get("total_cost"), run2.get("total_cost")),
                "total_tokens": _delta(run1.get("total_tokens"), run2.get("total_tokens")),
            },
        }

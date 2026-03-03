from __future__ import annotations

import json
from pathlib import Path


from sage.planning.state import PlanState, PlanStateManager, PlanTask


class TestPlanTask:
    def test_defaults(self) -> None:
        task = PlanTask(description="do something")
        assert task.status == "pending"
        assert task.result is None
        assert task.session_id is None

    def test_explicit_status(self) -> None:
        task = PlanTask(description="x", status="completed", result="done")
        assert task.status == "completed"
        assert task.result == "done"


class TestPlanState:
    def test_round_trip_json(self) -> None:
        plan = PlanState(
            plan_name="test",
            description="a test plan",
            tasks=[PlanTask(description="step 1"), PlanTask(description="step 2")],
        )
        raw = plan.model_dump_json()
        restored = PlanState.model_validate_json(raw)
        assert restored.plan_name == "test"
        assert len(restored.tasks) == 2
        assert restored.tasks[0].description == "step 1"

    def test_timestamps_populated(self) -> None:
        plan = PlanState(plan_name="t", description="d", tasks=[])
        assert plan.created_at > 0
        assert plan.updated_at > 0


class TestPlanStateManager:
    def test_save_and_load(self, tmp_path: Path) -> None:
        mgr = PlanStateManager(base_dir=tmp_path / "plans")
        plan = PlanState(
            plan_name="alpha",
            description="first plan",
            tasks=[PlanTask(description="task-a")],
        )
        mgr.save(plan)
        loaded = mgr.load("alpha")
        assert loaded is not None
        assert loaded.plan_name == "alpha"
        assert len(loaded.tasks) == 1

    def test_load_nonexistent_returns_none(self, tmp_path: Path) -> None:
        mgr = PlanStateManager(base_dir=tmp_path / "plans")
        assert mgr.load("nope") is None

    def test_list_active(self, tmp_path: Path) -> None:
        mgr = PlanStateManager(base_dir=tmp_path / "plans")
        assert mgr.list_active() == []
        mgr.save(PlanState(plan_name="a", description="", tasks=[]))
        mgr.save(PlanState(plan_name="b", description="", tasks=[]))
        assert sorted(mgr.list_active()) == ["a", "b"]

    def test_save_creates_valid_json(self, tmp_path: Path) -> None:
        mgr = PlanStateManager(base_dir=tmp_path / "plans")
        mgr.save(PlanState(plan_name="j", description="json check", tasks=[]))
        raw = (tmp_path / "plans" / "j.json").read_text()
        parsed = json.loads(raw)
        assert parsed["plan_name"] == "j"

    def test_save_updates_timestamp(self, tmp_path: Path) -> None:
        mgr = PlanStateManager(base_dir=tmp_path / "plans")
        plan = PlanState(plan_name="ts", description="", tasks=[])
        original = plan.updated_at
        mgr.save(plan)
        assert plan.updated_at >= original

    def test_overwrite_on_save(self, tmp_path: Path) -> None:
        mgr = PlanStateManager(base_dir=tmp_path / "plans")
        plan = PlanState(plan_name="ow", description="v1", tasks=[])
        mgr.save(plan)
        plan.description = "v2"
        mgr.save(plan)
        loaded = mgr.load("ow")
        assert loaded is not None
        assert loaded.description == "v2"

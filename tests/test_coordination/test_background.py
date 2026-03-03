"""Tests for sage.coordination.background — BackgroundTaskInfo and BackgroundTaskManager."""

from __future__ import annotations

import asyncio

import pytest

from sage.coordination.background import BackgroundTaskInfo, BackgroundTaskManager


# ---------------------------------------------------------------------------
# BackgroundTaskInfo tests
# ---------------------------------------------------------------------------


class TestBackgroundTaskInfo:
    def test_defaults(self) -> None:
        info = BackgroundTaskInfo(agent_name="researcher")
        assert info.agent_name == "researcher"
        assert info.status == "running"
        assert info.result is None
        assert info.error is None
        assert info.session_id is None
        assert info.notified is False
        assert info.completed_at is None
        assert info.task_id  # auto-generated, non-empty

    def test_explicit_task_id(self) -> None:
        info = BackgroundTaskInfo(task_id="custom123", agent_name="helper")
        assert info.task_id == "custom123"

    def test_unique_ids(self) -> None:
        a = BackgroundTaskInfo(agent_name="a")
        b = BackgroundTaskInfo(agent_name="b")
        assert a.task_id != b.task_id

    def test_mutable_status(self) -> None:
        info = BackgroundTaskInfo(agent_name="a")
        info.status = "completed"
        info.result = "done"
        assert info.status == "completed"
        assert info.result == "done"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockAgent:
    """Minimal agent-like object for BackgroundTaskManager tests."""

    def __init__(self, name: str, result: str = "ok", delay: float = 0.0, fail: bool = False):
        self.name = name
        self._result = result
        self._delay = delay
        self._fail = fail

    async def run(self, input: str) -> str:
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail:
            raise RuntimeError("agent failed")
        return self._result


# ---------------------------------------------------------------------------
# BackgroundTaskManager tests
# ---------------------------------------------------------------------------


class TestBackgroundTaskManager:
    @pytest.mark.asyncio
    async def test_launch_returns_task_id(self) -> None:
        mgr = BackgroundTaskManager()
        agent = _MockAgent("a", result="hello")
        task_id = await mgr.launch(agent, "do stuff")  # type: ignore[arg-type]
        assert isinstance(task_id, str)
        assert len(task_id) > 0

    @pytest.mark.asyncio
    async def test_launch_and_complete(self) -> None:
        mgr = BackgroundTaskManager()
        agent = _MockAgent("a", result="done")
        task_id = await mgr.launch(agent, "work")  # type: ignore[arg-type]
        # Allow the background task to finish.
        await asyncio.sleep(0.05)
        info = mgr.get(task_id)
        assert info is not None
        assert info.status == "completed"
        assert info.result == "done"
        assert info.completed_at is not None

    @pytest.mark.asyncio
    async def test_launch_failure(self) -> None:
        mgr = BackgroundTaskManager()
        agent = _MockAgent("a", fail=True)
        task_id = await mgr.launch(agent, "break")  # type: ignore[arg-type]
        await asyncio.sleep(0.05)
        info = mgr.get(task_id)
        assert info is not None
        assert info.status == "failed"
        assert "agent failed" in (info.error or "")

    @pytest.mark.asyncio
    async def test_cancel_running_task(self) -> None:
        mgr = BackgroundTaskManager()
        agent = _MockAgent("slow", delay=10.0)
        task_id = await mgr.launch(agent, "wait")  # type: ignore[arg-type]
        cancelled = mgr.cancel(task_id)
        assert cancelled is True
        info = mgr.get(task_id)
        assert info is not None
        assert info.status == "cancelled"

    def test_cancel_unknown_task(self) -> None:
        mgr = BackgroundTaskManager()
        assert mgr.cancel("nonexistent") is False

    def test_get_unknown_task(self) -> None:
        mgr = BackgroundTaskManager()
        assert mgr.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_tasks(self) -> None:
        mgr = BackgroundTaskManager()
        a1 = _MockAgent("a", result="r1")
        a2 = _MockAgent("b", result="r2", delay=10.0)
        await mgr.launch(a1, "t1")  # type: ignore[arg-type]
        await mgr.launch(a2, "t2")  # type: ignore[arg-type]
        await asyncio.sleep(0.05)
        all_tasks = mgr.list_tasks()
        assert len(all_tasks) == 2
        running = mgr.list_tasks(status="running")
        assert len(running) == 1
        assert running[0].agent_name == "b"
        # Cleanup: cancel the long-running task.
        for t in running:
            mgr.cancel(t.task_id)

    @pytest.mark.asyncio
    async def test_get_completed_unnotified(self) -> None:
        mgr = BackgroundTaskManager()
        agent = _MockAgent("a", result="x")
        task_id = await mgr.launch(agent, "go")  # type: ignore[arg-type]
        await asyncio.sleep(0.05)

        unnotified = mgr.get_completed_unnotified()
        assert len(unnotified) == 1
        assert unnotified[0].task_id == task_id

        mgr.mark_notified(task_id)
        assert mgr.get_completed_unnotified() == []

    @pytest.mark.asyncio
    async def test_count(self) -> None:
        mgr = BackgroundTaskManager()
        assert mgr.count() == 0
        agent = _MockAgent("a", delay=10.0)
        await mgr.launch(agent, "t")  # type: ignore[arg-type]
        assert mgr.count() == 1
        assert mgr.count(running_only=True) == 1
        # Cleanup.
        for t in mgr.list_tasks():
            mgr.cancel(t.task_id)

    @pytest.mark.asyncio
    async def test_cleanup(self) -> None:
        mgr = BackgroundTaskManager()
        agent = _MockAgent("a", result="y")
        task_id = await mgr.launch(agent, "go")  # type: ignore[arg-type]
        await asyncio.sleep(0.05)
        mgr.mark_notified(task_id)
        removed = mgr.cleanup()
        assert removed == 1
        assert mgr.count() == 0

    @pytest.mark.asyncio
    async def test_cleanup_keeps_running(self) -> None:
        mgr = BackgroundTaskManager()
        fast = _MockAgent("fast", result="done")
        slow = _MockAgent("slow", delay=10.0)
        fast_id = await mgr.launch(fast, "f")  # type: ignore[arg-type]
        await mgr.launch(slow, "s")  # type: ignore[arg-type]
        await asyncio.sleep(0.05)
        mgr.mark_notified(fast_id)
        removed = mgr.cleanup(keep_running=True)
        assert removed == 1
        assert mgr.count() == 1  # slow task still tracked
        # Cleanup.
        for t in mgr.list_tasks():
            mgr.cancel(t.task_id)

    @pytest.mark.asyncio
    async def test_session_id_stored(self) -> None:
        mgr = BackgroundTaskManager()
        agent = _MockAgent("a", result="ok")
        task_id = await mgr.launch(agent, "work", session_id="ses_abc")  # type: ignore[arg-type]
        info = mgr.get(task_id)
        assert info is not None
        assert info.session_id == "ses_abc"

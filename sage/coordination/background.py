"""Background task manager for non-blocking agent delegations."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from sage.agent import Agent

logger = logging.getLogger(__name__)


class BackgroundTaskInfo(BaseModel):
    """State container for a single background agent task.

    Each instance tracks one asynchronous delegation — its status,
    timing, result, and whether the orchestrator has been notified
    of completion.

    Usage::

        info = BackgroundTaskInfo(task_id="abc123", agent_name="researcher")
        info.status = "completed"
        info.result = "Found 3 relevant papers."
    """

    task_id: str = Field(default_factory=lambda: uuid4().hex)
    agent_name: str
    status: Literal["running", "completed", "failed", "cancelled"] = "running"
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = None
    result: str | None = None
    error: str | None = None
    session_id: str | None = None
    notified: bool = False


class BackgroundTaskManager:
    """In-memory manager for concurrent background agent tasks.

    Launches subagent runs as ``asyncio.Task`` instances, tracks their
    lifecycle, and exposes methods for polling / collecting results
    and cooperative cancellation.

    Usage::

        mgr = BackgroundTaskManager()
        task_id = await mgr.launch(agent, "Summarise the paper")
        # ... later ...
        info = mgr.get(task_id)
        if info and info.status == "completed":
            print(info.result)
    """

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._results: dict[str, BackgroundTaskInfo] = {}

    async def launch(
        self,
        agent: Agent,
        task_input: str,
        *,
        session_id: str | None = None,
    ) -> str:
        """Launch a subagent run in the background.

        Returns the ``task_id`` immediately.  The actual agent execution
        proceeds asynchronously; poll via :meth:`get` to check status.
        """
        task_id = uuid4().hex
        info = BackgroundTaskInfo(
            task_id=task_id,
            agent_name=agent.name,
            status="running",
            session_id=session_id,
        )
        self._results[task_id] = info

        async def _run() -> None:
            try:
                result = await agent.run(task_input)
                info.status = "completed"
                info.result = result
            except asyncio.CancelledError:
                info.status = "cancelled"
                raise
            except Exception as exc:
                info.status = "failed"
                info.error = str(exc)
                logger.error(
                    "Background task %s (%s) failed: %s",
                    task_id,
                    agent.name,
                    exc,
                    exc_info=True,
                )
            finally:
                info.completed_at = time.time()
                self._tasks.pop(task_id, None)

        self._tasks[task_id] = asyncio.create_task(_run())
        logger.info(
            "Launched background task %s for agent '%s'",
            task_id,
            agent.name,
        )
        return task_id

    def get(self, task_id: str) -> BackgroundTaskInfo | None:
        """Retrieve task info by ID, or ``None`` if not found."""
        return self._results.get(task_id)

    def cancel(self, task_id: str) -> bool:
        """Request cancellation of a running task.

        Returns ``True`` if the task was found and cancellation was
        requested, ``False`` otherwise (e.g. already completed or unknown ID).
        """
        task = self._tasks.get(task_id)
        if task is not None:
            task.cancel()
            info = self._results.get(task_id)
            if info is not None:
                info.status = "cancelled"
                info.completed_at = time.time()
            self._tasks.pop(task_id, None)
            logger.info("Cancelled background task %s", task_id)
            return True
        return False

    def list_tasks(
        self,
        *,
        status: str | None = None,
    ) -> list[BackgroundTaskInfo]:
        """List all tracked tasks, optionally filtered by status."""
        tasks = list(self._results.values())
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def get_completed_unnotified(self) -> list[BackgroundTaskInfo]:
        """Return completed/failed/cancelled tasks that haven't been notified yet."""
        return [t for t in self._results.values() if t.status != "running" and not t.notified]

    def mark_notified(self, task_id: str) -> None:
        """Mark a task as having been notified to the orchestrator."""
        info = self._results.get(task_id)
        if info is not None:
            info.notified = True

    def count(self, *, running_only: bool = False) -> int:
        """Return count of tracked tasks."""
        if running_only:
            return len(self._tasks)
        return len(self._results)

    def cleanup(self, *, keep_running: bool = True) -> int:
        """Remove completed/notified tasks from tracking.

        Returns the number of entries removed.
        """
        to_remove = [
            tid for tid, info in self._results.items() if info.status != "running" and info.notified
        ]
        if keep_running:
            to_remove = [tid for tid in to_remove if tid not in self._tasks]
        for tid in to_remove:
            del self._results[tid]
        return len(to_remove)

"""Plan persistence — structured models and a JSON-file state manager.

Plans are stored as JSON under ``.sage/plans/``.  The ``PlanStateManager``
provides save / load / list operations; the models are plain Pydantic v2.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class PlanTask(BaseModel):
    """A single task within a plan."""

    description: str
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: str | None = None
    session_id: str | None = None


class PlanState(BaseModel):
    """Top-level plan containing an ordered list of tasks."""

    plan_name: str
    description: str
    tasks: list[PlanTask]
    session_ids: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class PlanStateManager:
    """Persist and retrieve plans as JSON files.

    Args:
        base_dir: Directory for plan JSON files.  Created on init.
    """

    def __init__(self, base_dir: Path | str = ".sage/plans") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, plan: PlanState) -> Path:
        """Write *plan* to disk, updating ``updated_at``."""
        plan.updated_at = time.time()
        path = self.base_dir / f"{plan.plan_name}.json"
        path.write_text(plan.model_dump_json(indent=2))
        return path

    def load(self, name: str) -> PlanState | None:
        """Load a plan by name.  Returns ``None`` if it doesn't exist."""
        path = self.base_dir / f"{name}.json"
        if not path.exists():
            return None
        return PlanState.model_validate_json(path.read_text())

    def list_active(self) -> list[str]:
        """Return names of all plans on disk."""
        return [p.stem for p in self.base_dir.glob("*.json")]

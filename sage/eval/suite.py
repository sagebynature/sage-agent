"""Pydantic v2 models for eval test suites."""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from sage.eval.assertions import AssertionConfig


logger = logging.getLogger(__name__)


class TestCase(BaseModel):
    """A single test case within an eval suite."""

    id: str
    input: str
    context_files: list[str] = Field(default_factory=list)
    assertions: list[AssertionConfig] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    expected_output: str | None = None


class EvalSettings(BaseModel):
    """Settings for running an eval suite."""

    models: list[str] = Field(default_factory=lambda: ["gpt-4o"])
    runs_per_case: int = 1
    timeout: float = 60.0
    max_turns: int = 10


class TestSuite(BaseModel):
    """A collection of test cases for evaluating an agent."""

    name: str
    description: str = ""
    agent: str
    rubric: str = "default"
    test_cases: list[TestCase]
    settings: EvalSettings = Field(default_factory=EvalSettings)


def load_suite(path: str | Path) -> TestSuite:
    """Load a TestSuite from a YAML file."""
    resolved = Path(path)
    with open(resolved, "r", encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)
    return TestSuite.model_validate(data)

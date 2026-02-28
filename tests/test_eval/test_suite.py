"""Tests for sage.eval.suite — TestCase, TestSuite, EvalSettings, load_suite."""

from __future__ import annotations
import pytest
import yaml

from sage.eval.suite import EvalSettings, TestCase, TestSuite, load_suite


# ---------------------------------------------------------------------------
# EvalSettings defaults
# ---------------------------------------------------------------------------


def test_eval_settings_defaults() -> None:
    s = EvalSettings()
    assert s.models == ["gpt-4o"]
    assert s.runs_per_case == 1
    assert s.timeout == 60.0
    assert s.max_turns == 10


def test_eval_settings_custom() -> None:
    s = EvalSettings(models=["claude-3-5-haiku-20241022"], runs_per_case=3, timeout=30.0)
    assert s.models[0] == "claude-3-5-haiku-20241022"
    assert s.runs_per_case == 3
    assert s.timeout == 30.0


# ---------------------------------------------------------------------------
# TestCase
# ---------------------------------------------------------------------------


def test_test_case_minimal() -> None:
    tc = TestCase(id="tc-1", input="Hello world")
    assert tc.id == "tc-1"
    assert tc.input == "Hello world"
    assert tc.assertions == []
    assert tc.context_files == []
    assert tc.tags == []
    assert tc.expected_output is None


def test_test_case_with_tags() -> None:
    tc = TestCase(id="tc-2", input="test", tags=["smoke", "regression"])
    assert "smoke" in tc.tags


# ---------------------------------------------------------------------------
# TestSuite
# ---------------------------------------------------------------------------


def test_test_suite_minimal() -> None:
    suite = TestSuite(
        name="my-suite",
        agent="AGENTS.md",
        test_cases=[
            TestCase(id="tc-1", input="Hello"),
        ],
    )
    assert suite.name == "my-suite"
    assert len(suite.test_cases) == 1
    assert suite.rubric == "default"
    assert suite.description == ""


# ---------------------------------------------------------------------------
# load_suite — from YAML file
# ---------------------------------------------------------------------------


def test_load_suite_minimal(tmp_path) -> None:
    data = {
        "name": "example-suite",
        "agent": "AGENTS.md",
        "test_cases": [
            {"id": "tc-1", "input": "What is 2+2?"},
        ],
    }
    suite_file = tmp_path / "suite.yaml"
    suite_file.write_text(yaml.dump(data))

    suite = load_suite(suite_file)
    assert suite.name == "example-suite"
    assert suite.agent == str((tmp_path / "AGENTS.md").resolve())
    assert suite.suite_dir == str(tmp_path.resolve())
    assert len(suite.test_cases) == 1
    assert suite.test_cases[0].id == "tc-1"


def test_load_suite_with_assertions(tmp_path) -> None:
    data = {
        "name": "assertions-suite",
        "agent": "AGENTS.md",
        "test_cases": [
            {
                "id": "tc-1",
                "input": "Say hello",
                "assertions": [
                    {"type": "contains", "value": "hello"},
                    {"type": "not_contains", "value": "error"},
                ],
            }
        ],
    }
    suite_file = tmp_path / "suite.yaml"
    suite_file.write_text(yaml.dump(data))

    suite = load_suite(suite_file)
    assert len(suite.test_cases[0].assertions) == 2
    assert suite.test_cases[0].assertions[0].type == "contains"  # type: ignore[union-attr]


def test_load_suite_with_settings(tmp_path) -> None:
    data = {
        "name": "settings-suite",
        "agent": "AGENTS.md",
        "settings": {"models": ["gpt-4o-mini"], "timeout": 30.0, "runs_per_case": 2},
        "test_cases": [{"id": "tc-1", "input": "hi"}],
    }
    suite_file = tmp_path / "suite.yaml"
    suite_file.write_text(yaml.dump(data))

    suite = load_suite(suite_file)
    assert suite.settings.timeout == 30.0
    assert suite.settings.runs_per_case == 2
    assert suite.settings.models == ["gpt-4o-mini"]


def test_load_suite_invalid_yaml(tmp_path) -> None:
    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text("name: only-name\n")  # missing 'agent' and 'test_cases'

    with pytest.raises(Exception):
        load_suite(bad_file)


def test_load_suite_resolves_relative_paths(tmp_path) -> None:
    """Relative agent and context_files paths resolve against the YAML directory."""
    sub = tmp_path / "evals"
    sub.mkdir()
    data = {
        "name": "rel-suite",
        "agent": "../agents/AGENTS.md",
        "test_cases": [
            {
                "id": "tc-1",
                "input": "test",
                "context_files": ["./fixtures/sample.py", "../data/extra.py"],
            },
        ],
    }
    suite_file = sub / "suite.yaml"
    suite_file.write_text(yaml.dump(data))

    suite = load_suite(suite_file)
    assert suite.agent == str((tmp_path / "agents" / "AGENTS.md").resolve())
    assert suite.test_cases[0].context_files == [
        str((sub / "fixtures" / "sample.py").resolve()),
        str((tmp_path / "data" / "extra.py").resolve()),
    ]


def test_load_suite_nonexistent_file(tmp_path) -> None:
    with pytest.raises((FileNotFoundError, OSError)):
        load_suite(tmp_path / "missing.yaml")

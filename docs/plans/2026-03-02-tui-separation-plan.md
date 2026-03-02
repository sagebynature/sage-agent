# TUI Separation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract the TUI from `sage-agent` into a standalone `sage-tui` package at `~/sagebynature/sage-tui`.

**Architecture:** Simple extract — move `sage/cli/tui.py` to a new repo with its own `pyproject.toml` and CLI entry point. `sage-tui` depends on `sage-agent` for Agent, events, models, and config. No changes to `sage-agent` public API.

**Tech Stack:** Python 3.10+, Textual, Click, uv, pytest

---

### Task 1: Scaffold `sage-tui` repo

**Files:**
- Create: `~/sagebynature/sage-tui/pyproject.toml`
- Create: `~/sagebynature/sage-tui/sage_tui/__init__.py`
- Create: `~/sagebynature/sage-tui/sage_tui/__main__.py`
- Create: `~/sagebynature/sage-tui/tests/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p ~/sagebynature/sage-tui/sage_tui
mkdir -p ~/sagebynature/sage-tui/tests
```

**Step 2: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "sage-tui"
version = "0.1.0"
description = "Interactive TUI for Sage AI agent"
authors = [
    {name = "Sage Choi", email = "iamsagebynature@gmail.com"}
]
requires-python = ">=3.10"
readme = "README.md"
license = { file = "LICENSE" }
dependencies = [
    "sage-agent>=1.3.0",
    "textual>=0.50",
    "click>=8.0",
    "python-dotenv>=1.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1.0",
    "ruff>=0.5",
]

[project.scripts]
sage-tui = "sage_tui.cli:main"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py310"
line-length = 100
```

**Step 3: Create `sage_tui/__init__.py`**

```python
"""Sage TUI — Interactive terminal interface for Sage AI agents."""

__version__ = "0.1.0"
```

**Step 4: Create `sage_tui/__main__.py`**

```python
"""Allow running sage-tui as ``python -m sage_tui``."""

from sage_tui.cli import main

main()
```

**Step 5: Create `tests/__init__.py`**

Empty file.

**Step 6: Init git repo and commit**

```bash
cd ~/sagebynature/sage-tui
git init
git add pyproject.toml sage_tui/__init__.py sage_tui/__main__.py tests/__init__.py
git commit -m "chore: scaffold sage-tui package"
```

---

### Task 2: Create `sage_tui/cli.py` (standalone Click entry point)

**Files:**
- Create: `~/sagebynature/sage-tui/sage_tui/cli.py`
- Test: `~/sagebynature/sage-tui/tests/test_cli.py`

**Step 1: Write the failing test**

Create `tests/test_cli.py`:

```python
"""Tests for sage-tui CLI entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner


def test_main_shows_help() -> None:
    from sage_tui.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Launch the Sage interactive TUI" in result.output


def test_main_requires_config_or_config_toml() -> None:
    from sage_tui.cli import main

    runner = CliRunner()
    with patch("sage_tui.cli._load_main_config", return_value=None):
        result = runner.invoke(main, [])
    assert result.exit_code != 0
```

**Step 2: Run test to verify it fails**

```bash
cd ~/sagebynature/sage-tui
uv run pytest tests/test_cli.py -v
```

Expected: FAIL — `sage_tui.cli` does not exist.

**Step 3: Write the CLI module**

Create `sage_tui/cli.py`:

```python
"""Standalone CLI entry point for sage-tui."""

from __future__ import annotations

import logging
import logging.config
import sys
from pathlib import Path

import click
from dotenv import load_dotenv


def _setup_logging(verbose: bool = False) -> None:
    """Initialize basic logging."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s|%(name)s:%(funcName)s:L%(lineno)s|%(levelname)s %(message)s",
    )
    if verbose:
        logging.getLogger("sage").setLevel(logging.DEBUG)


def _load_main_config(config_path: str | None) -> "MainConfig | None":
    """Load main config from a TOML file path."""
    from sage.main_config import load_main_config, resolve_main_config_path

    resolved = resolve_main_config_path(config_path)
    return load_main_config(resolved)


def _resolve_primary_agent(
    main_config: "MainConfig | None",
    config_file_path: Path | None = None,
) -> str:
    """Resolve the primary agent config path from MainConfig."""
    from sage.exceptions import ConfigError

    if main_config is None:
        raise ConfigError(
            "No config.toml found. Provide --agent-config or create a config.toml with a 'primary' field."
        )

    raw_agents_dir = Path(main_config.agents_dir)
    if not raw_agents_dir.is_absolute() and config_file_path is not None:
        agents_dir = (config_file_path.parent / raw_agents_dir).resolve()
    else:
        agents_dir = raw_agents_dir

    if main_config.primary:
        candidate = agents_dir / f"{main_config.primary}.md"
        if candidate.exists():
            return str(candidate)
        candidate = agents_dir / main_config.primary / "AGENTS.md"
        if candidate.exists():
            return str(candidate)
        raise ConfigError(
            f"Primary agent '{main_config.primary}' not found at "
            f"'{agents_dir / (main_config.primary + '.md')}' or "
            f"'{agents_dir / main_config.primary / 'AGENTS.md'}'"
        )

    candidate = agents_dir / "AGENTS.md"
    if candidate.exists():
        return str(candidate)
    raise ConfigError(
        f"No 'primary' set in config.toml and no AGENTS.md found in '{agents_dir}'. "
        "Provide --agent-config or set 'primary' in config.toml."
    )


@click.command()
@click.option(
    "--agent-config",
    "-c",
    "config_path",
    required=False,
    default=None,
    type=click.Path(exists=True),
    help="Path to AGENTS.md or directory containing AGENTS.md (inferred from config.toml if omitted)",
)
@click.option(
    "--config",
    "main_config_path",
    default=None,
    help="Path to main config.toml (also reads SAGE_CONFIG_PATH env var)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable debug logging",
)
def main(config_path: str | None, main_config_path: str | None, verbose: bool) -> None:
    """Launch the Sage interactive TUI."""
    load_dotenv()
    _setup_logging(verbose)

    from sage.exceptions import ConfigError
    from sage.main_config import resolve_and_apply_env

    main_config = _load_main_config(main_config_path)
    resolve_and_apply_env(main_config)

    if config_path is None:
        try:
            from sage.main_config import resolve_main_config_path

            resolved_path = resolve_main_config_path(main_config_path)
            config_path = _resolve_primary_agent(main_config, resolved_path)
        except ConfigError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    path = Path(config_path)
    if path.is_dir():
        path = path / "AGENTS.md"

    from sage_tui.app import SageTUIApp

    app = SageTUIApp(config_path=path, central=main_config)
    app.run()
```

**Step 4: Run tests to verify they pass**

```bash
cd ~/sagebynature/sage-tui
uv run pytest tests/test_cli.py -v
```

Expected: PASS (help test passes; config test passes because `_load_main_config` is mocked to return None).

**Step 5: Commit**

```bash
git add sage_tui/cli.py tests/test_cli.py
git commit -m "feat: add standalone sage-tui CLI entry point"
```

---

### Task 3: Move TUI app code to `sage_tui/app.py`

**Files:**
- Create: `~/sagebynature/sage-tui/sage_tui/app.py`
- Source: `~/sagebynature/sage-agent/sage/cli/tui.py` (copy, then modify imports)

**Step 1: Copy the TUI source**

```bash
cp ~/sagebynature/sage-agent/sage/cli/tui.py ~/sagebynature/sage-tui/sage_tui/app.py
```

**Step 2: Update the module docstring**

Change line 3 from:
```python
Provides the ``SageTUIApp`` class launched by ``sage tui --config=<path>``.
```
to:
```python
Provides the ``SageTUIApp`` class launched by ``sage-tui --config=<path>``.
```

**Step 3: Update the logger name**

No change needed — `logging.getLogger(__name__)` will automatically resolve to `sage_tui.app`.

**Step 4: Verify all `sage.*` imports are valid**

The following imports in `app.py` all reference `sage-agent` (installed as a dependency) — no changes needed:

```python
from sage.agent import Agent
from sage.orchestrator.parallel import Orchestrator
from sage.events import (DelegationStarted, LLMStreamDelta, LLMTurnStarted, ToolCompleted, ToolStarted)
from sage.permissions.interactive import InteractivePermissionHandler
from sage.permissions.policy import PolicyPermissionHandler
from sage.models import CompletionResult, Message, Usage
from sage.main_config import MainConfig
```

**Step 5: Commit**

```bash
cd ~/sagebynature/sage-tui
git add sage_tui/app.py
git commit -m "feat: move SageTUIApp from sage-agent to sage-tui"
```

---

### Task 4: Move TUI tests to `sage-tui`

**Files:**
- Create: `~/sagebynature/sage-tui/tests/test_app.py`
- Create: `~/sagebynature/sage-tui/tests/conftest.py`
- Source: `~/sagebynature/sage-agent/tests/test_cli/test_tui.py`

**Step 1: Copy the test file**

```bash
cp ~/sagebynature/sage-agent/tests/test_cli/test_tui.py ~/sagebynature/sage-tui/tests/test_app.py
```

**Step 2: Update imports in `tests/test_app.py`**

Replace all `sage.cli.tui` imports with `sage_tui.app`:

```python
# OLD:
from sage.cli.tui import (
    AssistantEntry, ChatPanel, HistoryInput, LogPanel,
    StatusPanel, ThinkingEntry, ToolEntry, TUILogHandler, UserEntry,
)

# NEW:
from sage_tui.app import (
    AssistantEntry, ChatPanel, HistoryInput, LogPanel,
    StatusPanel, ThinkingEntry, ToolEntry, TUILogHandler, UserEntry,
)
```

Also update the lazy imports inside test functions:

```python
# OLD:
from sage.cli.tui import SageTUIApp
from sage.cli.tui import PermissionScreen
from sage.cli.tui import _wire_interactive_permissions

# NEW:
from sage_tui.app import SageTUIApp
from sage_tui.app import PermissionScreen
from sage_tui.app import _wire_interactive_permissions
```

Update mock patch targets:

```python
# OLD:
with patch("sage.cli.tui.Agent.from_config", return_value=mock_agent):

# NEW:
with patch("sage_tui.app.Agent.from_config", return_value=mock_agent):
```

**Step 3: Create empty `tests/conftest.py`**

```python
"""Shared test fixtures for sage-tui."""
```

**Step 4: Run all tests**

```bash
cd ~/sagebynature/sage-tui
uv run pytest tests/ -v
```

Expected: All tests PASS. These are pure widget tests with mocked agents — no real agent needed.

**Step 5: Commit**

```bash
git add tests/test_app.py tests/conftest.py
git commit -m "feat: move TUI widget tests from sage-agent"
```

---

### Task 5: Install `sage-tui` in dev mode and smoke test

**Step 1: Install sage-agent as editable dependency**

```bash
cd ~/sagebynature/sage-tui
uv pip install -e ../sage-agent
uv pip install -e ".[dev]"
```

**Step 2: Run the full test suite**

```bash
cd ~/sagebynature/sage-tui
uv run pytest tests/ -v
```

Expected: All tests PASS.

**Step 3: Verify the CLI entry point**

```bash
cd ~/sagebynature/sage-tui
sage-tui --help
```

Expected: Shows help text with `--agent-config`, `--config`, `--verbose` options.

**Step 4: Commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix: resolve dev install issues"
```

---

### Task 6: Remove TUI from `sage-agent`

**Files:**
- Delete: `~/sagebynature/sage-agent/sage/cli/tui.py`
- Delete: `~/sagebynature/sage-agent/tests/test_cli/test_tui.py`
- Modify: `~/sagebynature/sage-agent/pyproject.toml:25` — remove `textual>=0.50`
- Modify: `~/sagebynature/sage-agent/sage/cli/main.py:362-387` — remove `tui` command

**Step 1: Delete TUI files**

```bash
cd ~/sagebynature/sage-agent
rm sage/cli/tui.py
rm tests/test_cli/test_tui.py
```

**Step 2: Remove `textual` from `pyproject.toml` dependencies**

In `~/sagebynature/sage-agent/pyproject.toml`, remove the line:

```
    "textual>=0.50",
```

from the `dependencies` list (line 25).

**Step 3: Remove `tui` command from `sage/cli/main.py`**

Delete lines 362-388 (the `@cli.command()` block for `tui`):

```python
@cli.command()
@click.option(
    "--agent-config",
    "-c",
    "config_path",
    ...
)
@click.pass_context
def tui(ctx: click.Context, config_path: str | None) -> None:
    """Launch the interactive TUI for an agent config.
    ...
    """
    from sage.cli.tui import SageTUIApp
    ...
    app.run()
```

**Step 4: Run sage-agent tests to verify nothing broke**

```bash
cd ~/sagebynature/sage-agent
uv run pytest tests/ -v --ignore=tests/test_cli/test_tui.py
```

Expected: All remaining tests PASS. No test should import `sage.cli.tui`.

**Step 5: Verify `sage` CLI still works without TUI**

```bash
sage --help
sage agent --help
sage exec --help
```

Expected: All commands listed except `tui`.

**Step 6: Commit**

```bash
cd ~/sagebynature/sage-agent
git add -A
git commit -m "refactor: remove TUI code from sage-agent (moved to sage-tui)"
```

---

### Task 7: Add LICENSE and verify end-to-end

**Files:**
- Create: `~/sagebynature/sage-tui/LICENSE`

**Step 1: Copy LICENSE from sage-agent**

```bash
cp ~/sagebynature/sage-agent/LICENSE ~/sagebynature/sage-tui/LICENSE
```

**Step 2: Run sage-tui tests one final time**

```bash
cd ~/sagebynature/sage-tui
uv run pytest tests/ -v
```

Expected: All tests PASS.

**Step 3: Verify the CLI launches (if config.toml is available)**

```bash
sage-tui --help
```

Expected: Help output with description "Launch the Sage interactive TUI."

**Step 4: Commit**

```bash
cd ~/sagebynature/sage-tui
git add LICENSE
git commit -m "chore: add MIT license"
```

---

## Summary

| Task | Description | Repo |
|------|-------------|------|
| 1 | Scaffold sage-tui repo | sage-tui |
| 2 | Create standalone CLI entry point | sage-tui |
| 3 | Move TUI app code | sage-tui |
| 4 | Move TUI tests | sage-tui |
| 5 | Dev install and smoke test | sage-tui |
| 6 | Remove TUI from sage-agent | sage-agent |
| 7 | Add LICENSE and final verification | sage-tui |

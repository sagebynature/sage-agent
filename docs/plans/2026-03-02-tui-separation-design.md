# TUI Separation Design

**Date:** 2026-03-02
**Status:** Approved

## Summary

Extract the Sage TUI from `sage-agent` into a standalone `sage-tui` package at `~/sagebynature/sage-tui`. The TUI becomes an independent repo and installable package that depends on `sage-agent`. The `sage-agent` repo keeps its name and drops all TUI/Textual code.

## Decision Record

- **2-package split**: `sage-agent` (core) + `sage-tui` (UI). No shared `sage-core` package — `sage-tui` imports directly from `sage-agent`.
- **Separate repos**: `~/sagebynature/sage-agent/` and `~/sagebynature/sage-tui/`. Not a monorepo.
- **No repo rename**: `sage-agent` stays as-is.
- **Standalone CLI**: `sage-tui` command (not a subcommand of `sage`).
- **Clean break**: `textual` removed entirely from `sage-agent` dependencies.

## New Repo: `sage-tui`

### Structure

```
~/sagebynature/sage-tui/
├── pyproject.toml
├── sage_tui/
│   ├── __init__.py          # version, public exports
│   ├── app.py               # SageTUIApp (from sage/cli/tui.py)
│   ├── __main__.py          # python -m sage_tui support
│   └── cli.py               # Click entry point for sage-tui command
├── tests/
│   ├── conftest.py
│   └── test_app.py          # from tests/test_cli/test_tui.py
└── LICENSE
```

### Package Metadata

- **Python package:** `sage_tui`
- **PyPI name:** `sage-tui`
- **Entry point:** `sage-tui = "sage_tui.cli:main"`
- **Dependencies:** `sage-agent>=1.3.0`, `textual>=0.50`

### `sage_tui/cli.py`

Standalone Click command that:
1. Loads `MainConfig` from `config.toml` (reusing `sage.main_config` utilities)
2. Resolves the primary agent config path
3. Launches `SageTUIApp`

Replaces the `tui()` function currently in `sage/cli/main.py`.

### `sage_tui/app.py`

Direct move of `sage/cli/tui.py` with import path updates:
- All `sage.*` imports remain valid (Agent, events, models, config, permissions, orchestrator)
- Module-internal references change from `sage.cli.tui` to `sage_tui.app`

### Tests

- Move `tests/test_cli/test_tui.py` to `sage-tui/tests/test_app.py`
- Update imports from `sage.cli.tui` to `sage_tui.app`
- Test structure and assertions unchanged (pure widget tests with mocked agents)

## Changes to `sage-agent`

### Files Removed
- `sage/cli/tui.py`
- `tests/test_cli/test_tui.py`

### Files Modified
- `pyproject.toml`: Remove `textual>=0.50` from dependencies
- `sage/cli/main.py`: Remove `tui` command (lines 362-387)

### Unchanged
- All agent core code (agent.py, events.py, models.py, config.py)
- All other CLI commands (agent run, exec, eval, init, tool list)
- All non-TUI tests
- Public API surface

## Coupling Points

The `sage-tui` package depends on these `sage-agent` interfaces:

| Interface | Module | Usage |
|-----------|--------|-------|
| `Agent.from_config(path, central)` | `sage.agent` | Create agent instance |
| `Agent.run(input)` / `Agent.stream(input)` | `sage.agent` | Execute agent |
| `Agent.on(event_class, callback)` | `sage.agent` | Subscribe to events |
| `Agent.close()` | `sage.agent` | Cleanup |
| Agent properties (`.name`, `.model`, `.skills`, `.subagents`) | `sage.agent` | Status display |
| `Agent.reset_session()` / `.get_usage_stats()` | `sage.agent` | Session management |
| Event dataclasses | `sage.events` | TUI event handlers |
| `InteractivePermissionHandler` | `sage.permissions.interactive` | Permission modal |
| `PolicyPermissionHandler` | `sage.permissions.policy` | Permission detection |
| `Orchestrator.run_parallel()` | `sage.orchestrator.parallel` | Subagent orchestration |
| `MainConfig`, `load_main_config`, etc. | `sage.main_config` | Config loading |
| `Message`, `CompletionResult`, `Usage` | `sage.models` | Title generation |
| `load_config` | `sage.config` | Agent config loading |

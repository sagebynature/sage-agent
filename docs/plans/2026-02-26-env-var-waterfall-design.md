# Env Var Waterfall Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Resolve required env vars from config.toml `[env]` section with `${VAR}` expansion, falling back to `.env` / `os.environ`.

**Architecture:** Add an `env` dict field to `MainConfig`, a `resolve_and_apply_env()` function that expands `${VAR}` references against `os.environ` and injects resolved values back into `os.environ`. Called early in CLI startup after `load_dotenv()` and `load_main_config()`.

**Tech Stack:** Python, Pydantic v2, tomllib, re, pytest

---

## Design Summary

```toml
[env]
AZURE_AI_API_KEY = "${AZURE_AI_API_KEY}"
AZURE_AI_API_BASE = "https://d-ue2-aicorepltfm-aisvcs.services.ai.azure.com"
MIXED = "prefix-${SOME_VAR}-suffix"
```

- Literal values used as-is, `${VAR}` references resolved from `os.environ`
- Unresolved references raise `ConfigError` listing all missing vars
- Resolved values injected into `os.environ` (config.toml wins)
- Execution order: `load_dotenv()` -> `load_main_config()` -> `resolve_and_apply_env()`

---

### Task 1: Add `env` field to `MainConfig` (with tests)

**Files:**
- Modify: `sage/main_config.py:58-64`
- Test: `tests/test_main_config.py`

**Step 1: Write the failing test**

Add to `tests/test_main_config.py` inside `class TestMainConfig`:

```python
def test_env_field_defaults_empty(self) -> None:
    cfg = MainConfig()
    assert cfg.env == {}

def test_env_field_accepts_dict(self) -> None:
    cfg = MainConfig(env={"FOO": "bar", "BAZ": "${QUX}"})
    assert cfg.env == {"FOO": "bar", "BAZ": "${QUX}"}

def test_env_field_in_toml(self, tmp_path: Path) -> None:
    toml_path = _write_toml(
        tmp_path / "config.toml",
        '[env]\nAZURE_AI_API_KEY = "${AZURE_AI_API_KEY}"\nAZURE_AI_API_BASE = "https://example.com"\n',
    )
    cfg = load_main_config(toml_path)
    assert cfg is not None
    assert cfg.env == {
        "AZURE_AI_API_KEY": "${AZURE_AI_API_KEY}",
        "AZURE_AI_API_BASE": "https://example.com",
    }
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_main_config.py::TestMainConfig::test_env_field_defaults_empty tests/test_main_config.py::TestMainConfig::test_env_field_accepts_dict tests/test_main_config.py::TestMainConfig::test_env_field_in_toml -v`
Expected: FAIL — `MainConfig` does not have `env` field yet.

**Step 3: Write minimal implementation**

In `sage/main_config.py`, add to the `MainConfig` class:

```python
class MainConfig(BaseModel):
    """Top-level main configuration loaded from config.toml."""

    model_config = ConfigDict(extra="forbid")

    env: dict[str, str] = Field(default_factory=dict)
    defaults: ConfigOverrides = Field(default_factory=ConfigOverrides)
    agents: dict[str, AgentOverrides] = Field(default_factory=dict)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_main_config.py::TestMainConfig -v`
Expected: PASS

**Step 5: Commit**

```bash
git add sage/main_config.py tests/test_main_config.py
git commit -m "feat(config): add env field to MainConfig"
```

---

### Task 2: Implement `resolve_and_apply_env()` (with tests)

**Files:**
- Modify: `sage/main_config.py` (add function after `load_main_config`)
- Test: `tests/test_main_config.py`

**Step 1: Write the failing tests**

Add a new test class to `tests/test_main_config.py`:

```python
from sage.main_config import resolve_and_apply_env

class TestResolveAndApplyEnv:
    def test_literal_values_set_in_environ(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MY_VAR", raising=False)
        cfg = MainConfig(env={"MY_VAR": "hello"})
        resolve_and_apply_env(cfg)
        assert os.environ["MY_VAR"] == "hello"

    def test_reference_resolved_from_environ(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SOURCE_VAR", "secret123")
        monkeypatch.delenv("TARGET_VAR", raising=False)
        cfg = MainConfig(env={"TARGET_VAR": "${SOURCE_VAR}"})
        resolve_and_apply_env(cfg)
        assert os.environ["TARGET_VAR"] == "secret123"

    def test_mixed_literal_and_reference(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOST", "example.com")
        cfg = MainConfig(env={"URL": "https://${HOST}/api"})
        resolve_and_apply_env(cfg)
        assert os.environ["URL"] == "https://example.com/api"

    def test_multiple_references_in_one_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("USER", "admin")
        monkeypatch.setenv("PASS", "s3cret")
        cfg = MainConfig(env={"CREDS": "${USER}:${PASS}"})
        resolve_and_apply_env(cfg)
        assert os.environ["CREDS"] == "admin:s3cret"

    def test_missing_reference_raises_config_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MISSING_VAR", raising=False)
        cfg = MainConfig(env={"KEY": "${MISSING_VAR}"})
        with pytest.raises(ConfigError, match="MISSING_VAR"):
            resolve_and_apply_env(cfg)

    def test_multiple_missing_all_reported(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("A", raising=False)
        monkeypatch.delenv("B", raising=False)
        cfg = MainConfig(env={"X": "${A}", "Y": "${B}"})
        with pytest.raises(ConfigError, match="A") as exc_info:
            resolve_and_apply_env(cfg)
        assert "B" in str(exc_info.value)

    def test_config_toml_overwrites_existing_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MY_VAR", "old_value")
        cfg = MainConfig(env={"MY_VAR": "new_value"})
        resolve_and_apply_env(cfg)
        assert os.environ["MY_VAR"] == "new_value"

    def test_none_config_is_noop(self) -> None:
        resolve_and_apply_env(None)  # should not raise

    def test_empty_env_is_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = MainConfig()
        resolve_and_apply_env(cfg)  # should not raise

    def test_self_reference_resolved_from_existing_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """${VAR} in env.VAR resolves from os.environ (set by .env)."""
        monkeypatch.setenv("API_KEY", "from_dotenv")
        cfg = MainConfig(env={"API_KEY": "${API_KEY}"})
        resolve_and_apply_env(cfg)
        assert os.environ["API_KEY"] == "from_dotenv"
```

Also add `import os` at the top of the test file if not already present.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_main_config.py::TestResolveAndApplyEnv -v`
Expected: FAIL — `resolve_and_apply_env` does not exist yet.

**Step 3: Write minimal implementation**

Add to `sage/main_config.py` after `load_main_config()`, also add `import re` at the top:

```python
_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def resolve_and_apply_env(config: MainConfig | None) -> None:
    """Resolve ``${VAR}`` references in ``config.env`` and set ``os.environ``.

    Resolution order:
      1. ``[env]`` values in config.toml (may contain ``${VAR}`` references)
      2. ``os.environ`` (already populated by ``load_dotenv()``)

    Raises :class:`~sage.exceptions.ConfigError` listing all unresolved
    variable references.
    """
    if config is None or not config.env:
        return

    missing: list[str] = []
    resolved: dict[str, str] = {}

    for key, value in config.env.items():
        unresolved_in_value: list[str] = []

        def _replace(match: re.Match[str]) -> str:
            var_name = match.group(1)
            env_val = os.environ.get(var_name)
            if env_val is None:
                unresolved_in_value.append(var_name)
                return match.group(0)  # keep placeholder for error msg
            return env_val

        resolved[key] = _ENV_VAR_RE.sub(_replace, value)
        missing.extend(unresolved_in_value)

    if missing:
        unique = sorted(set(missing))
        raise ConfigError(
            f"Unresolved env var references in [env]: {', '.join(unique)}"
        )

    for key, value in resolved.items():
        os.environ[key] = value
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_main_config.py::TestResolveAndApplyEnv -v`
Expected: PASS

**Step 5: Commit**

```bash
git add sage/main_config.py tests/test_main_config.py
git commit -m "feat(config): add resolve_and_apply_env for env var waterfall"
```

---

### Task 3: Wire into CLI startup

**Files:**
- Modify: `sage/cli/main.py:86-92`

**Step 1: Write the failing test (manual verification)**

No new test file — this is a 2-line wiring change. Verify by running existing tests first:

Run: `uv run pytest tests/test_main_config.py -v`
Expected: PASS (all existing + new tests)

**Step 2: Modify CLI**

In `sage/cli/main.py`, update the `cli()` function:

```python
@click.pass_context
def cli(
    ctx: click.Context, main_config_path: str | None, log_config_path: str | None, verbose: bool
) -> None:
    """Sage - AI agent definition and deployment."""
    load_dotenv()
    _setup_logging(log_config_path, verbose)
    ctx.ensure_object(dict)
    from sage.main_config import resolve_main_config_path, load_main_config, resolve_and_apply_env

    resolved = resolve_main_config_path(main_config_path)
    ctx.obj["main_config"] = load_main_config(resolved)
    resolve_and_apply_env(ctx.obj["main_config"])
```

**Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS

**Step 4: Commit**

```bash
git add sage/cli/main.py
git commit -m "feat(cli): wire resolve_and_apply_env into startup"
```

---

### Task 4: Update config.toml with `[env]` section

**Files:**
- Modify: `config.toml`

**Step 1: Add [env] section to config.toml**

Add at the top of `config.toml`, before `[defaults]`:

```toml
# ─── Environment Variables ──────────────────────────────────────────────────
# Resolved at startup. Values can reference env vars with ${VAR} syntax.
# Resolution order: config.toml [env] > .env file > os.environ
# Unresolved ${VAR} references cause a startup error.
[env]
AZURE_AI_API_KEY = "${AZURE_AI_API_KEY}"
AZURE_AI_API_BASE = "https://d-ue2-aicorepltfm-aisvcs.services.ai.azure.com"
```

**Step 2: Verify config loads**

Run: `uv run pytest tests/test_main_config.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add config.toml
git commit -m "feat(config): add [env] section to config.toml"
```

---

### Task 5: Update docstring in main_config.py module

**Files:**
- Modify: `sage/main_config.py:1-8`

**Step 1: Update module docstring**

```python
"""Main configuration loading, resolution, and merge for Sage.

Provides a TOML-based main config with a three-tier override system::

    agent .md frontmatter     (highest priority)
    [agents.<name>] in TOML   (agent-specific overrides)
    [defaults] in TOML         (global defaults)

Environment variables are resolved from the ``[env]`` section using
``${VAR}`` syntax, with values sourced from ``os.environ`` (populated
by ``load_dotenv()``).  Resolved values are injected back into
``os.environ`` so downstream libraries (e.g. litellm) pick them up.
"""
```

**Step 2: Commit**

```bash
git add sage/main_config.py
git commit -m "docs: update main_config module docstring for [env] section"
```

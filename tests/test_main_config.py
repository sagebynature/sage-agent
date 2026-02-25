"""Tests for main configuration loading, resolution, and merge."""

from __future__ import annotations

from pathlib import Path

import pytest

from sage.main_config import (
    AgentOverrides,
    MainConfig,
    ConfigOverrides,
    load_main_config,
    merge_agent_config,
    resolve_main_config_path,
)
from sage.config import load_config
from sage.exceptions import ConfigError

import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_toml(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _write_md(path: Path, frontmatter: dict[str, object], body: str = "") -> Path:
    content = "---\n" + yaml.dump(frontmatter) + "---\n"
    if body:
        content += "\n" + body
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------


class TestConfigOverrides:
    def test_all_none_by_default(self) -> None:
        overrides = ConfigOverrides()
        assert overrides.model is None
        assert overrides.model_params is None
        assert overrides.max_turns is None
        assert overrides.permissions is None
        assert overrides.context is None
        assert overrides.tools is None
        assert overrides.mcp_servers is None

    def test_model_dump_excludes_none(self) -> None:
        overrides = ConfigOverrides(model="gpt-4o", max_turns=20)
        dumped = overrides.model_dump(exclude_none=True)
        assert dumped == {"model": "gpt-4o", "max_turns": 20}

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(Exception):
            ConfigOverrides(unknown_field="value")  # type: ignore[call-arg]


class TestAgentOverrides:
    def test_inherits_config_overrides(self) -> None:
        overrides = AgentOverrides(model="gpt-4o", skills_dir="my_skills")
        assert overrides.model == "gpt-4o"
        assert overrides.skills_dir == "my_skills"

    def test_memory_field(self) -> None:
        overrides = AgentOverrides(memory={"backend": "sqlite", "path": "mem.db"})  # type: ignore[arg-type]
        assert overrides.memory is not None
        assert overrides.memory.backend == "sqlite"


class TestMainConfig:
    def test_empty_config(self) -> None:
        cfg = MainConfig()
        assert cfg.defaults.model is None
        assert cfg.agents == {}

    def test_with_defaults(self) -> None:
        cfg = MainConfig(defaults=ConfigOverrides(model="gpt-4o", max_turns=20))
        assert cfg.defaults.model == "gpt-4o"
        assert cfg.defaults.max_turns == 20

    def test_with_agents(self) -> None:
        cfg = MainConfig(
            agents={
                "researcher": AgentOverrides(model="gpt-4o", max_turns=30),
                "summarizer": AgentOverrides(model="gpt-4o-mini"),
            }
        )
        assert cfg.agents["researcher"].model == "gpt-4o"
        assert cfg.agents["researcher"].max_turns == 30
        assert cfg.agents["summarizer"].model == "gpt-4o-mini"

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(Exception):
            MainConfig(unknown_section="value")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# resolve_main_config_path tests
# ---------------------------------------------------------------------------


class TestResolveMainConfigPath:
    def test_cli_path_found(self, tmp_path: Path) -> None:
        toml_path = tmp_path / "config.toml"
        toml_path.write_text("[defaults]\n")
        assert resolve_main_config_path(str(toml_path)) == toml_path

    def test_cli_path_not_found_falls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SAGE_CONFIG_PATH", raising=False)
        monkeypatch.chdir(tmp_path)
        result = resolve_main_config_path(str(tmp_path / "nonexistent.toml"))
        # No config.toml in cwd or default location → None
        assert result is None

    def test_env_var_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        toml_path = tmp_path / "config.toml"
        toml_path.write_text("[defaults]\n")
        monkeypatch.setenv("SAGE_CONFIG_PATH", str(toml_path))
        assert resolve_main_config_path() == toml_path

    def test_env_var_not_found_falls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SAGE_CONFIG_PATH", str(tmp_path / "nope.toml"))
        monkeypatch.chdir(tmp_path)
        result = resolve_main_config_path()
        # No config.toml in cwd or default location → None
        assert result is None

    def test_cli_takes_priority_over_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cli_path = tmp_path / "cli.toml"
        cli_path.write_text("[defaults]\n")
        env_path = tmp_path / "env.toml"
        env_path.write_text("[defaults]\n")
        monkeypatch.setenv("SAGE_CONFIG_PATH", str(env_path))
        assert resolve_main_config_path(str(cli_path)) == cli_path

    def test_cwd_config_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SAGE_CONFIG_PATH", raising=False)
        cwd_toml = tmp_path / "config.toml"
        cwd_toml.write_text("[defaults]\n")
        monkeypatch.chdir(tmp_path)
        assert resolve_main_config_path() == cwd_toml

    def test_cli_not_found_falls_back_to_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SAGE_CONFIG_PATH", raising=False)
        cwd_toml = tmp_path / "config.toml"
        cwd_toml.write_text("[defaults]\n")
        monkeypatch.chdir(tmp_path)
        result = resolve_main_config_path(str(tmp_path / "missing.toml"))
        assert result == cwd_toml

    def test_env_not_found_falls_back_to_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SAGE_CONFIG_PATH", str(tmp_path / "nope.toml"))
        cwd_toml = tmp_path / "config.toml"
        cwd_toml.write_text("[defaults]\n")
        monkeypatch.chdir(tmp_path)
        result = resolve_main_config_path()
        assert result == cwd_toml

    def test_default_path_not_found_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("SAGE_CONFIG_PATH", raising=False)
        monkeypatch.chdir(tmp_path)  # empty dir, no config.toml
        result = resolve_main_config_path()
        # Result is either None (no default) or a valid path (developer machine)
        assert result is None or result.exists()


# ---------------------------------------------------------------------------
# load_main_config tests
# ---------------------------------------------------------------------------


class TestLoadMainConfig:
    def test_none_returns_none(self) -> None:
        assert load_main_config(None) is None

    def test_loads_minimal_toml(self, tmp_path: Path) -> None:
        toml_path = _write_toml(
            tmp_path / "config.toml",
            '[defaults]\nmodel = "azure_ai/gpt-4o"\nmax_turns = 20\n',
        )
        cfg = load_main_config(toml_path)
        assert cfg is not None
        assert cfg.defaults.model == "azure_ai/gpt-4o"
        assert cfg.defaults.max_turns == 20

    def test_loads_full_toml(self, tmp_path: Path) -> None:
        toml_path = _write_toml(
            tmp_path / "config.toml",
            """\
[defaults]
model = "azure_ai/gpt-4o"
max_turns = 20
tools = ["sage.tools.builtins"]

[defaults.model_params]
temperature = 0.7

[defaults.permissions]
default = "allow"

[agents.research-assistant]
model = "azure_ai/gpt-4o"
max_turns = 30

[agents.research-assistant.model_params]
temperature = 0.3

[agents.summarizer]
model = "azure_ai/gpt-4o-mini"
max_turns = 5
""",
        )
        cfg = load_main_config(toml_path)
        assert cfg is not None
        assert cfg.defaults.model == "azure_ai/gpt-4o"
        assert cfg.defaults.model_params is not None
        assert cfg.defaults.model_params.temperature == 0.7
        assert cfg.defaults.permissions is not None
        assert cfg.defaults.permissions.default == "allow"
        assert "research-assistant" in cfg.agents
        assert cfg.agents["research-assistant"].max_turns == 30
        assert cfg.agents["research-assistant"].model_params is not None
        assert cfg.agents["research-assistant"].model_params.temperature == 0.3
        assert cfg.agents["summarizer"].model == "azure_ai/gpt-4o-mini"

    def test_invalid_toml_raises(self, tmp_path: Path) -> None:
        toml_path = _write_toml(tmp_path / "bad.toml", "not valid toml [[[")
        with pytest.raises(ConfigError, match="Failed to parse"):
            load_main_config(toml_path)

    def test_unknown_keys_rejected(self, tmp_path: Path) -> None:
        toml_path = _write_toml(
            tmp_path / "config.toml",
            '[defaults]\nmodel = "gpt-4o"\nunknown_key = "bad"\n',
        )
        with pytest.raises(ConfigError, match="Invalid main config"):
            load_main_config(toml_path)

    def test_unreadable_file_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.toml"
        with pytest.raises(ConfigError, match="Failed to read"):
            # File doesn't exist, should raise OSError internally
            load_main_config(missing)


# ---------------------------------------------------------------------------
# merge_agent_config tests
# ---------------------------------------------------------------------------


class TestMergeAgentConfig:
    def test_no_central_returns_metadata(self) -> None:
        metadata = {"name": "agent", "model": "gpt-4o"}
        assert merge_agent_config(metadata, None) is metadata

    def test_defaults_applied(self) -> None:
        central = MainConfig(defaults=ConfigOverrides(model="gpt-4o", max_turns=20))
        metadata: dict[str, object] = {"name": "agent"}
        merged = merge_agent_config(metadata, central)
        assert merged["model"] == "gpt-4o"
        assert merged["max_turns"] == 20
        assert merged["name"] == "agent"

    def test_agent_overrides_applied(self) -> None:
        central = MainConfig(
            defaults=ConfigOverrides(model="gpt-4o", max_turns=20),
            agents={"my-agent": AgentOverrides(max_turns=30)},
        )
        metadata: dict[str, object] = {"name": "my-agent"}
        merged = merge_agent_config(metadata, central, "my-agent")
        assert merged["model"] == "gpt-4o"  # from defaults
        assert merged["max_turns"] == 30  # from agent overrides

    def test_frontmatter_overrides_everything(self) -> None:
        central = MainConfig(
            defaults=ConfigOverrides(model="gpt-4o", max_turns=20),
            agents={"my-agent": AgentOverrides(max_turns=30)},
        )
        metadata: dict[str, object] = {"name": "my-agent", "max_turns": 50}
        merged = merge_agent_config(metadata, central, "my-agent")
        assert merged["max_turns"] == 50  # frontmatter wins

    def test_no_matching_agent_override(self) -> None:
        central = MainConfig(
            defaults=ConfigOverrides(model="gpt-4o"),
            agents={"other-agent": AgentOverrides(max_turns=30)},
        )
        metadata: dict[str, object] = {"name": "my-agent"}
        merged = merge_agent_config(metadata, central, "my-agent")
        assert merged["model"] == "gpt-4o"
        assert "max_turns" not in merged  # not in defaults or agent overrides

    def test_top_level_replacement_semantics(self) -> None:
        """Nested objects like model_params are replaced, not deep-merged."""
        central = MainConfig(
            defaults=ConfigOverrides(
                model_params={"temperature": 0.7, "max_tokens": 1024}  # type: ignore[arg-type]
            )
        )
        metadata: dict[str, object] = {
            "name": "agent",
            "model": "gpt-4o",
            "model_params": {"temperature": 0.3},
        }
        merged = merge_agent_config(metadata, central, "agent")
        # Frontmatter model_params replaces entirely — no max_tokens carried over
        assert merged["model_params"] == {"temperature": 0.3}

    def test_none_agent_name(self) -> None:
        central = MainConfig(
            defaults=ConfigOverrides(model="gpt-4o"),
        )
        metadata: dict[str, object] = {"name": "agent"}
        merged = merge_agent_config(metadata, central, None)
        assert merged["model"] == "gpt-4o"


# ---------------------------------------------------------------------------
# Integration: load_config with main config
# ---------------------------------------------------------------------------


class TestLoadConfigWithCentral:
    def test_model_from_central_defaults(self, tmp_path: Path) -> None:
        """Agent .md with no model resolves it from central defaults."""
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "research-assistant", "description": "Research agent"},
            body="You are a researcher.",
        )
        central = MainConfig(defaults=ConfigOverrides(model="azure_ai/gpt-4o", max_turns=20))
        config = load_config(cfg_path, central=central)
        assert config.name == "research-assistant"
        assert config.model == "azure_ai/gpt-4o"
        assert config.max_turns == 20

    def test_model_from_agent_overrides(self, tmp_path: Path) -> None:
        """Per-agent override takes priority over defaults."""
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "summarizer", "description": "Summarizes text"},
        )
        central = MainConfig(
            defaults=ConfigOverrides(model="azure_ai/gpt-4o", max_turns=20),
            agents={"summarizer": AgentOverrides(model="azure_ai/gpt-4o-mini", max_turns=5)},
        )
        config = load_config(cfg_path, central=central)
        assert config.model == "azure_ai/gpt-4o-mini"
        assert config.max_turns == 5

    def test_frontmatter_overrides_central(self, tmp_path: Path) -> None:
        """Frontmatter values take highest priority."""
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "agent", "model": "custom/model", "max_turns": 99},
        )
        central = MainConfig(defaults=ConfigOverrides(model="azure_ai/gpt-4o", max_turns=20))
        config = load_config(cfg_path, central=central)
        assert config.model == "custom/model"
        assert config.max_turns == 99

    def test_no_model_anywhere_raises(self, tmp_path: Path) -> None:
        """ConfigError when no model in frontmatter or main config."""
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "agent", "description": "No model here"},
        )
        central = MainConfig()  # no defaults
        with pytest.raises(ConfigError, match="model.*is required"):
            load_config(cfg_path, central=central)

    def test_no_model_without_central_raises(self, tmp_path: Path) -> None:
        """ConfigError when no model and no main config."""
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "agent"},
        )
        with pytest.raises(ConfigError, match="model.*is required"):
            load_config(cfg_path)

    def test_backward_compat_no_central(self, tmp_path: Path) -> None:
        """Existing configs with model work without main config."""
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "agent", "model": "gpt-4o"},
        )
        config = load_config(cfg_path)
        assert config.name == "agent"
        assert config.model == "gpt-4o"

    def test_tools_from_central(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "agent", "description": "Tool user"},
        )
        central = MainConfig(
            defaults=ConfigOverrides(model="gpt-4o", tools=["sage.tools.builtins"])
        )
        config = load_config(cfg_path, central=central)
        assert config.tools == ["sage.tools.builtins"]

    def test_permissions_from_central(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "agent", "description": "Perm test"},
        )
        central = MainConfig(
            defaults=ConfigOverrides(
                model="gpt-4o",
                permissions={"default": "deny"},  # type: ignore[arg-type]
            )
        )
        config = load_config(cfg_path, central=central)
        assert config.permissions is not None
        assert config.permissions.default == "deny"

    def test_config_ref_subagent_merged_with_central(self, tmp_path: Path) -> None:
        """Config-ref subagents are merged with main config."""
        _write_md(
            tmp_path / "sub.md",
            {"name": "sub-agent", "description": "A subagent"},
            body="Sub prompt.",
        )
        cfg_path = _write_md(
            tmp_path / "main.md",
            {
                "name": "orchestrator",
                "model": "gpt-4o",
                "subagents": [{"config": "sub.md"}],
            },
        )
        central = MainConfig(defaults=ConfigOverrides(model="azure_ai/gpt-4o", max_turns=25))
        config = load_config(cfg_path, central=central)
        sub = config.subagents[0]
        assert sub.name == "sub-agent"
        assert sub.model == "azure_ai/gpt-4o"  # from central defaults
        assert sub.max_turns == 25

    def test_inline_subagent_not_merged(self, tmp_path: Path) -> None:
        """Inline subagents are NOT merged — must be fully specified."""
        cfg_path = _write_md(
            tmp_path / "main.md",
            {
                "name": "orchestrator",
                "model": "gpt-4o",
                "subagents": [
                    {"name": "inline", "model": "gpt-4o-mini"},
                ],
            },
        )
        central = MainConfig(defaults=ConfigOverrides(max_turns=99))
        config = load_config(cfg_path, central=central)
        sub = config.subagents[0]
        assert sub.model == "gpt-4o-mini"
        # max_turns is NOT inherited from central for inline subagents
        assert sub.max_turns == 10  # AgentConfig default

    def test_inline_subagent_without_model_raises(self, tmp_path: Path) -> None:
        """Inline subagent without model raises ConfigError."""
        cfg_path = _write_md(
            tmp_path / "main.md",
            {
                "name": "orchestrator",
                "model": "gpt-4o",
                "subagents": [
                    {"name": "inline-no-model"},
                ],
            },
        )
        central = MainConfig(defaults=ConfigOverrides(model="gpt-4o"))
        with pytest.raises(ConfigError, match="Inline subagent.*must specify 'model'"):
            load_config(cfg_path, central=central)

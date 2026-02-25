"""Tests for the configuration loading and validation system.

TDD red-phase: these tests are written for the NEW markdown/frontmatter format.
They WILL FAIL until Task 2 (AgentConfig rewrite) and Task 6 (load_config rewrite)
are complete.
"""

from __future__ import annotations

import logging
import sys
import types
from pathlib import Path

import pytest
import yaml

from sage.config import AgentConfig, MCPServerConfig, MemoryConfig, ModelParams, load_config
from sage.exceptions import ConfigError
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_merge_agent_config(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("sage.main_config")

    def merge_agent_config(metadata: dict, central: object | None, agent_name: str | None) -> dict:
        _ = (central, agent_name)
        return metadata

    module.merge_agent_config = merge_agent_config  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sage.main_config", module)


def _write_md(path: Path, frontmatter: dict, body: str = "") -> Path:
    """Write a markdown file with YAML frontmatter and optional body."""
    content = "---\n" + yaml.dump(frontmatter) + "---\n"
    if body:
        content += "\n" + body
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# load_config — markdown / frontmatter format
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_valid_config(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "research-assistant", "model": "azure/gpt-4o", "max_turns": 15},
            body="You are a research assistant.",
        )
        config = load_config(cfg_path)

        assert config.name == "research-assistant"
        assert config.model == "azure/gpt-4o"
        assert config.max_turns == 15

    def test_default_values(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "minimal", "model": "gpt-4o"},
        )
        config = load_config(cfg_path)

        assert config.description == ""
        assert config.extensions == []
        assert config.max_turns == 10
        assert config.memory is None
        assert config.subagents == []
        assert config.mcp_servers == []

    def test_body_becomes_system_prompt(self, tmp_path: Path) -> None:
        body_text = "You are an expert analyst. Always cite your sources."
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "analyst", "model": "gpt-4o"},
            body=body_text,
        )
        config = load_config(cfg_path)
        assert config._body == body_text

    def test_empty_body_allowed(self, tmp_path: Path) -> None:
        """Frontmatter-only .md (no body) is valid; _body == ''."""
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "minimal", "model": "gpt-4o"},
        )
        config = load_config(cfg_path)
        assert config._body == ""

    def test_yaml_file_rejected(self, tmp_path: Path) -> None:
        """load_config should reject .yaml files outright."""
        yaml_path = tmp_path / "agent.yaml"
        yaml_path.write_text("name: test\nmodel: gpt-4o\n", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(yaml_path)

    def test_no_frontmatter_raises_error(self, tmp_path: Path) -> None:
        """A .md file without --- frontmatter delimiters should raise ConfigError."""
        md_path = tmp_path / "bad.md"
        md_path.write_text("name: test\nmodel: gpt-4o\n", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(md_path)

    def test_missing_config_file_raises_config_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="Config file not found"):
            load_config(tmp_path / "nonexistent.md")

    def test_invalid_yaml_frontmatter_raises_config_error(self, tmp_path: Path) -> None:
        md_path = tmp_path / "bad.md"
        md_path.write_text("---\nname: test\n  bad_indent: [\n---\n", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(md_path)

    def test_missing_required_field_raises_config_error(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "incomplete.md",
            {"model": "gpt-4o"},
        )
        with pytest.raises(ConfigError, match="Invalid agent configuration"):
            load_config(cfg_path)

    def test_nested_subagent_config(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "orchestrator",
                "model": "azure/gpt-4o",
                "subagents": [
                    {"name": "summarizer", "model": "azure/gpt-4o-mini"},
                    {"name": "researcher", "model": "azure/gpt-4o", "max_turns": 20},
                ],
            },
        )
        config = load_config(cfg_path)

        assert len(config.subagents) == 2
        assert config.subagents[0].name == "summarizer"
        assert config.subagents[0].model == "azure/gpt-4o-mini"
        assert config.subagents[1].name == "researcher"
        assert config.subagents[1].max_turns == 20

    def test_mcp_server_config_stdio(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "agent",
                "model": "gpt-4o",
                "mcp_servers": [
                    {
                        "transport": "stdio",
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                        "env": {"HOME": "/tmp"},
                    }
                ],
            },
        )
        config = load_config(cfg_path)

        assert len(config.mcp_servers) == 1
        mcp = config.mcp_servers[0]
        assert mcp.transport == "stdio"
        assert mcp.command == "npx"
        assert mcp.args == ["-y", "@modelcontextprotocol/server-filesystem"]
        assert mcp.env == {"HOME": "/tmp"}
        assert mcp.url is None

    def test_mcp_server_config_sse(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "agent",
                "model": "gpt-4o",
                "mcp_servers": [{"transport": "sse", "url": "http://localhost:8080/sse"}],
            },
        )
        config = load_config(cfg_path)

        mcp = config.mcp_servers[0]
        assert mcp.transport == "sse"
        assert mcp.url == "http://localhost:8080/sse"
        assert mcp.command is None

    def test_extensions_field_parsed(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "agent",
                "model": "gpt-4o",
                "extensions": ["myapp.tools"],
            },
        )
        config = load_config(cfg_path)
        assert config.extensions == ["myapp.tools"]

    def test_memory_config(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "agent",
                "model": "gpt-4o",
                "memory": {
                    "backend": "sqlite",
                    "path": "./data/memory.db",
                    "compaction_threshold": 100,
                },
            },
        )
        config = load_config(cfg_path)
        assert config.memory is not None
        assert config.memory.backend == "sqlite"
        assert config.memory.path == "./data/memory.db"
        assert config.memory.compaction_threshold == 100

    def test_description_field_in_file(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "research-assistant",
                "model": "azure/gpt-4o",
                "description": "A thorough research assistant",
            },
            body="You are a research assistant.",
        )
        config = load_config(cfg_path)
        assert config.description == "A thorough research assistant"

    def test_full_example_config(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "research-assistant",
                "model": "azure/gpt-4o",
                "description": "My research assistant",
                "extensions": ["myproject.tools"],
                "memory": {
                    "backend": "sqlite",
                    "path": "./data/memory.db",
                    "compaction_threshold": 100,
                },
                "max_turns": 15,
                "mcp_servers": [
                    {
                        "transport": "stdio",
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                    }
                ],
                "subagents": [
                    {"name": "summarizer", "model": "azure/gpt-4o-mini"},
                ],
            },
            body="You are a research assistant. Provide detailed, accurate information.",
        )
        config = load_config(cfg_path)

        assert config.name == "research-assistant"
        assert config.description == "My research assistant"
        assert (
            config._body == "You are a research assistant. Provide detailed, accurate information."
        )
        assert config.extensions == ["myproject.tools"]
        assert config.memory is not None
        assert config.memory.compaction_threshold == 100
        assert config.max_turns == 15
        assert len(config.mcp_servers) == 1
        assert len(config.subagents) == 1
        assert config.subagents[0].name == "summarizer"

    def test_load_config_from_directory(self, tmp_path: Path) -> None:
        """load_config accepts a directory containing AGENTS.md."""
        _write_md(
            tmp_path / "AGENTS.md",
            {"name": "dir-agent", "model": "gpt-4o"},
            body="Agent loaded from directory.",
        )
        config = load_config(tmp_path)
        assert config.name == "dir-agent"
        assert config._body.strip() == "Agent loaded from directory."

    def test_load_config_from_directory_missing_agents_md(self, tmp_path: Path) -> None:
        """load_config raises ConfigError when directory has no AGENTS.md."""
        with pytest.raises(ConfigError, match="Config file not found"):
            load_config(tmp_path)


# ---------------------------------------------------------------------------
# Pydantic model unit tests
# ---------------------------------------------------------------------------


class TestMCPServerConfig:
    def test_defaults(self) -> None:
        cfg = MCPServerConfig()
        assert cfg.transport == "stdio"
        assert cfg.command is None
        assert cfg.url is None
        assert cfg.args == []
        assert cfg.env == {}

    def test_invalid_transport_rejected(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            MCPServerConfig(transport="grpc")  # type: ignore[arg-type]


class TestMemoryConfig:
    def test_defaults(self) -> None:
        cfg = MemoryConfig()
        assert cfg.backend == "sqlite"
        assert cfg.path == "memory.db"
        assert cfg.embedding == "text-embedding-3-large"
        assert cfg.compaction_threshold == 50


class TestAgentConfig:
    def test_requires_name_and_model(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            AgentConfig()  # type: ignore[call-arg]

    def test_minimal_creation(self) -> None:
        cfg = AgentConfig(name="test", model="gpt-4o")
        assert cfg.name == "test"
        assert cfg.model == "gpt-4o"

    def test_description_field(self) -> None:
        cfg = AgentConfig(name="t", model="gpt-4o", description="My agent")
        assert cfg.description == "My agent"

    def test_description_defaults_to_empty(self) -> None:
        cfg = AgentConfig(name="t", model="gpt-4o")
        assert cfg.description == ""

    def test_persona_field_is_rejected(self) -> None:
        """persona field no longer exists — hard cutover, zero backward compat."""
        with pytest.raises(ValidationError):
            AgentConfig(name="t", model="gpt-4o", persona="You are helpful.")  # type: ignore[call-arg]

    def test_body_private_attr_accessible(self) -> None:
        """_body is a PrivateAttr — accessible on instance, not in model_dump."""
        cfg = AgentConfig(name="t", model="gpt-4o")
        assert cfg._body == ""
        assert "_body" not in cfg.model_dump()

    def test_config_ref_requires_no_name_or_model(self) -> None:
        # A subagent ref with only 'config' set is valid at parse time.
        cfg = AgentConfig(config="researcher.md")
        assert cfg.config == "researcher.md"
        assert cfg.name == ""
        assert cfg.model == ""

    def test_name_required_without_config(self) -> None:
        with pytest.raises(Exception, match="name"):
            AgentConfig(model="gpt-4o")

    def test_model_defaults_to_empty_without_config(self) -> None:
        """model is no longer required at AgentConfig level (validated post-merge)."""
        cfg = AgentConfig(name="agent")
        assert cfg.model == ""


# ---------------------------------------------------------------------------
# Subagent config-file references (.md)
# ---------------------------------------------------------------------------


class TestSubagentConfigRef:
    def test_subagent_loaded_from_md_file(self, tmp_path: Path) -> None:
        _write_md(
            tmp_path / "researcher.md",
            {"name": "researcher", "model": "azure_ai/gpt-4o", "max_turns": 15},
            body="You are a researcher.",
        )
        cfg_path = _write_md(
            tmp_path / "orchestrator.md",
            {
                "name": "orchestrator",
                "model": "azure_ai/gpt-4o",
                "subagents": [{"config": "researcher.md"}],
            },
        )
        config = load_config(cfg_path)

        assert len(config.subagents) == 1
        sub = config.subagents[0]
        assert sub.name == "researcher"
        assert sub.model == "azure_ai/gpt-4o"
        assert sub._body == "You are a researcher."
        assert sub.max_turns == 15

    def test_multiple_subagent_refs(self, tmp_path: Path) -> None:
        _write_md(tmp_path / "a.md", {"name": "agent-a", "model": "azure_ai/gpt-4o"})
        _write_md(tmp_path / "b.md", {"name": "agent-b", "model": "azure_ai/gpt-4o-mini"})
        cfg_path = _write_md(
            tmp_path / "main.md",
            {
                "name": "lead",
                "model": "azure_ai/gpt-4o",
                "subagents": [{"config": "a.md"}, {"config": "b.md"}],
            },
        )
        config = load_config(cfg_path)
        assert [s.name for s in config.subagents] == ["agent-a", "agent-b"]

    def test_ref_body_loaded_from_subagent_file(self, tmp_path: Path) -> None:
        sub_dir = tmp_path / "agents"
        sub_dir.mkdir()
        _write_md(
            sub_dir / "sub.md",
            {"name": "sub", "model": "gpt-4o"},
            body="Sub system prompt.",
        )
        cfg_path = _write_md(
            tmp_path / "main.md",
            {
                "name": "main",
                "model": "gpt-4o",
                "subagents": [{"config": "agents/sub.md"}],
            },
        )
        config = load_config(cfg_path)
        assert config.subagents[0]._body == "Sub system prompt."

    def test_missing_ref_file_raises_config_error(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "main.md",
            {
                "name": "main",
                "model": "gpt-4o",
                "subagents": [{"config": "nonexistent.md"}],
            },
        )
        with pytest.raises(ConfigError, match="Config file not found"):
            load_config(cfg_path)

    def test_inline_and_ref_subagents_coexist(self, tmp_path: Path) -> None:
        _write_md(tmp_path / "external.md", {"name": "external", "model": "gpt-4o"})
        cfg_path = _write_md(
            tmp_path / "main.md",
            {
                "name": "main",
                "model": "gpt-4o",
                "subagents": [
                    {"config": "external.md"},
                    {"name": "inline", "model": "gpt-4o-mini"},
                ],
            },
        )
        config = load_config(cfg_path)
        names = [s.name for s in config.subagents]
        assert "external" in names
        assert "inline" in names

    def test_yaml_subagent_ref_rejected(self, tmp_path: Path) -> None:
        """Config refs pointing at .yaml files should be rejected."""
        yaml_path = tmp_path / "sub.yaml"
        yaml_path.write_text("name: sub\nmodel: gpt-4o\n", encoding="utf-8")
        cfg_path = _write_md(
            tmp_path / "main.md",
            {
                "name": "main",
                "model": "gpt-4o",
                "subagents": [{"config": "sub.yaml"}],
            },
        )
        with pytest.raises(ConfigError):
            load_config(cfg_path)


class TestDirectorySubagentRef:
    """Tests for plain-string subagent references (directory-based)."""

    def test_string_subagent_coerced_to_config_ref(self) -> None:
        """A plain string in the subagents list becomes {config: <string>}."""
        cfg = AgentConfig(
            name="orch",
            model="gpt-4o",
            subagents=["research_agent"],  # type: ignore[list-item]
        )
        assert len(cfg.subagents) == 1
        assert cfg.subagents[0].config == "research_agent"

    def test_mixed_string_and_dict_subagents(self) -> None:
        """Strings and dicts can coexist in the subagents list."""
        cfg = AgentConfig(
            name="orch",
            model="gpt-4o",
            subagents=[
                "research_agent",  # type: ignore[list-item]
                {"name": "inline", "model": "gpt-4o-mini"},
                {"config": "other.md"},
            ],
        )
        assert len(cfg.subagents) == 3
        assert cfg.subagents[0].config == "research_agent"
        assert cfg.subagents[1].name == "inline"
        assert cfg.subagents[2].config == "other.md"

    def test_string_subagent_resolved_from_directory(self, tmp_path: Path) -> None:
        """A plain string subagent resolves to a directory containing AGENTS.md."""
        sub_dir = tmp_path / "research_agent"
        sub_dir.mkdir()
        _write_md(
            sub_dir / "AGENTS.md",
            {"name": "researcher", "model": "azure_ai/gpt-4o", "max_turns": 15},
            body="You are a researcher.",
        )
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "orchestrator",
                "model": "azure_ai/gpt-4o",
                "subagents": ["research_agent"],
            },
        )
        config = load_config(cfg_path)

        assert len(config.subagents) == 1
        sub = config.subagents[0]
        assert sub.name == "researcher"
        assert sub.model == "azure_ai/gpt-4o"
        assert sub._body == "You are a researcher."
        assert sub.max_turns == 15

    def test_multiple_string_subagents_resolved(self, tmp_path: Path) -> None:
        """Multiple plain-string subagents resolve correctly."""
        for name, agent_name, model in [
            ("research_agent", "researcher", "azure_ai/gpt-4o"),
            ("summarize_agent", "summarizer", "azure_ai/gpt-4o-mini"),
        ]:
            d = tmp_path / name
            d.mkdir()
            _write_md(d / "AGENTS.md", {"name": agent_name, "model": model})
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "orchestrator",
                "model": "gpt-4o",
                "subagents": ["research_agent", "summarize_agent"],
            },
        )
        config = load_config(cfg_path)

        assert len(config.subagents) == 2
        assert config.subagents[0].name == "researcher"
        assert config.subagents[1].name == "summarizer"

    def test_string_and_inline_subagents_coexist_in_md(self, tmp_path: Path) -> None:
        """A mix of plain strings and inline dicts works end-to-end."""
        sub_dir = tmp_path / "research_agent"
        sub_dir.mkdir()
        _write_md(
            sub_dir / "AGENTS.md",
            {"name": "researcher", "model": "gpt-4o"},
        )
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "orchestrator",
                "model": "gpt-4o",
                "subagents": [
                    "research_agent",
                    {"name": "inline-helper", "model": "gpt-4o-mini"},
                ],
            },
        )
        config = load_config(cfg_path)

        assert len(config.subagents) == 2
        names = [s.name for s in config.subagents]
        assert "researcher" in names
        assert "inline-helper" in names

    def test_string_subagent_missing_directory_raises(self, tmp_path: Path) -> None:
        """A plain string pointing to a nonexistent directory raises ConfigError."""
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "orchestrator",
                "model": "gpt-4o",
                "subagents": ["nonexistent_agent"],
            },
        )
        with pytest.raises(ConfigError, match="Config file not found"):
            load_config(cfg_path)


# ---------------------------------------------------------------------------
# ModelParams tests
# ---------------------------------------------------------------------------


class TestModelParams:
    def test_defaults_all_none(self) -> None:
        params = ModelParams()
        assert params.temperature is None
        assert params.max_tokens is None
        assert params.top_p is None
        assert params.top_k is None
        assert params.frequency_penalty is None
        assert params.presence_penalty is None
        assert params.seed is None
        assert params.stop is None
        assert params.timeout is None
        assert params.response_format is None

    def test_to_kwargs_empty_when_nothing_set(self) -> None:
        params = ModelParams()
        assert params.to_kwargs() == {}

    def test_to_kwargs_excludes_none_values(self) -> None:
        params = ModelParams(temperature=0.7, max_tokens=1024)
        kwargs = params.to_kwargs()
        assert kwargs == {"temperature": 0.7, "max_tokens": 1024}

    def test_to_kwargs_all_fields(self) -> None:
        params = ModelParams(
            temperature=0.3,
            max_tokens=4096,
            top_p=0.9,
            top_k=50,
            frequency_penalty=0.1,
            presence_penalty=0.2,
            seed=42,
            stop=["END", "DONE"],
            timeout=30.0,
            response_format={"type": "json_object"},
        )
        kwargs = params.to_kwargs()
        assert kwargs["temperature"] == 0.3
        assert kwargs["max_tokens"] == 4096
        assert kwargs["top_p"] == 0.9
        assert kwargs["top_k"] == 50
        assert kwargs["frequency_penalty"] == 0.1
        assert kwargs["presence_penalty"] == 0.2
        assert kwargs["seed"] == 42
        assert kwargs["stop"] == ["END", "DONE"]
        assert kwargs["timeout"] == 30.0
        assert kwargs["response_format"] == {"type": "json_object"}

    def test_agent_config_default_model_params(self) -> None:
        cfg = AgentConfig(name="test", model="gpt-4o")
        assert cfg.model_params.to_kwargs() == {}

    def test_model_params_loaded_from_md(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "researcher",
                "model": "azure_ai/gpt-4o",
                "model_params": {
                    "temperature": 0.3,
                    "max_tokens": 4096,
                    "seed": 42,
                    "stop": ["END", "DONE"],
                    "timeout": 30.0,
                },
            },
        )
        config = load_config(cfg_path)
        assert config.model_params.temperature == 0.3
        assert config.model_params.max_tokens == 4096
        assert config.model_params.seed == 42
        assert config.model_params.stop == ["END", "DONE"]
        assert config.model_params.timeout == 30.0
        assert config.model_params.top_p is None

    def test_model_params_to_kwargs_omits_unset(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "agent",
                "model": "gpt-4o",
                "model_params": {"temperature": 0.5},
            },
        )
        config = load_config(cfg_path)
        kwargs = config.model_params.to_kwargs()
        assert kwargs == {"temperature": 0.5}
        assert "max_tokens" not in kwargs
        assert "seed" not in kwargs


# ---------------------------------------------------------------------------
# Skills config tests
# ---------------------------------------------------------------------------


class TestSkillsConfig:
    def test_skills_dir_defaults_to_none(self) -> None:
        cfg = AgentConfig(name="test", model="gpt-4o")
        assert cfg.skills_dir is None

    def test_skills_dir_set_from_md(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "agent", "model": "gpt-4o", "skills_dir": "my_skills"},
        )
        config = load_config(cfg_path)
        assert config.skills_dir == "my_skills"

    def test_skills_dir_not_set_when_absent(self, tmp_path: Path) -> None:
        cfg_path = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "agent", "model": "gpt-4o"},
        )
        config = load_config(cfg_path)
        assert config.skills_dir is None


class TestConfigLogging:
    def test_load_config_logs_debug(self, caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
        """load_config should log DEBUG with file path and agent name."""
        config_file = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "test-agent", "model": "gpt-4o"},
        )

        with caplog.at_level(logging.DEBUG, logger="sage.config"):
            load_config(str(config_file))

        all_messages = " ".join(r.message for r in caplog.records)
        assert "test-agent" in all_messages or "AGENTS.md" in all_messages, (
            f"Expected agent name or path in logs, got: {all_messages}"
        )


class TestPermissionConfig:
    def test_permission_field_parsed(self, tmp_path: Path) -> None:
        config_file = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "test",
                "model": "gpt-4o",
                "permission": {"shell": "allow"},
            },
            body="You are a test agent.",
        )
        config = load_config(str(config_file))
        assert config.permission is not None
        assert config.permission.shell == "allow"

    def test_empty_permission_block(self, tmp_path: Path) -> None:
        config_file = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "test",
                "model": "gpt-4o",
                "permission": {},
            },
            body="Agent prompt.",
        )
        config = load_config(str(config_file))
        assert config.permission is not None
        from sage.config import Permission

        assert config.permission == Permission()

    def test_permission_none_by_default(self, tmp_path: Path) -> None:
        config_file = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "test", "model": "gpt-4o"},
            body="Agent prompt.",
        )
        config = load_config(str(config_file))
        assert config.permission is None

    def test_old_tools_field_rejected(self, tmp_path: Path) -> None:
        config_file = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "test",
                "model": "gpt-4o",
                "tools": ["shell"],
            },
            body="Agent prompt.",
        )
        with pytest.raises(ConfigError, match="Invalid agent configuration"):
            load_config(str(config_file))

    def test_old_permissions_field_rejected(self, tmp_path: Path) -> None:
        config_file = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "test",
                "model": "gpt-4o",
                "permissions": {"default": "deny"},
            },
            body="Agent prompt.",
        )
        with pytest.raises(ConfigError, match="Invalid agent configuration"):
            load_config(str(config_file))


class TestContextConfig:
    def test_context_config_parsed(self, tmp_path: Path) -> None:
        config_file = _write_md(
            tmp_path / "AGENTS.md",
            {
                "name": "test",
                "model": "gpt-4o",
                "context": {
                    "compaction_threshold": 0.8,
                    "reserve_tokens": 8192,
                    "prune_tool_outputs": True,
                    "tool_output_max_chars": 3000,
                },
            },
            body="Agent prompt.",
        )
        config = load_config(str(config_file))
        assert config.context is not None
        assert config.context.compaction_threshold == 0.8
        assert config.context.reserve_tokens == 8192
        assert config.context.prune_tool_outputs is True
        assert config.context.tool_output_max_chars == 3000

    def test_no_context_is_none(self, tmp_path: Path) -> None:
        config_file = _write_md(
            tmp_path / "AGENTS.md",
            {"name": "test", "model": "gpt-4o"},
            body="Agent prompt.",
        )
        config = load_config(str(config_file))
        assert config.context is None


# ---------------------------------------------------------------------------
# Permission model tests (NEW)
# ---------------------------------------------------------------------------


class TestPermissionModel:
    """Tests for the new Permission model (config-level permissions)."""

    def test_permission_all_none_fields(self) -> None:
        """Permission model instantiates with all fields defaulting to None."""
        from sage.config import Permission

        perm = Permission()
        assert perm.read is None
        assert perm.edit is None
        assert perm.shell is None
        assert perm.web is None
        assert perm.memory is None
        assert perm.task is None

    def test_permission_string_action(self) -> None:
        """Permission field accepts plain string action."""
        from sage.config import Permission

        perm = Permission(read="allow", shell="deny", web="ask")
        assert perm.read == "allow"
        assert perm.shell == "deny"
        assert perm.web == "ask"

    def test_permission_dict_pattern(self) -> None:
        """Permission field accepts dict with string-to-action pattern mapping."""
        from sage.config import Permission

        perm = Permission(
            shell={"*": "deny", "git log*": "allow"},
            memory={"store": "ask", "recall": "allow"},
        )
        assert perm.shell == {"*": "deny", "git log*": "allow"}
        assert perm.memory == {"store": "ask", "recall": "allow"}

    def test_permission_mixed_string_and_dict(self) -> None:
        """Permission model supports mix of string and dict fields."""
        from sage.config import Permission

        perm = Permission(read="allow", shell={"*": "deny"}, task={"compile": "allow"})
        assert perm.read == "allow"
        assert perm.shell == {"*": "deny"}
        assert perm.task == {"compile": "allow"}

    def test_permission_extra_field_allowed(self) -> None:
        """Permission model allows extra fields (for MCP/custom tool categories)."""
        from sage.config import Permission

        perm = Permission(
            read="allow",
            custom_mcp_tool="ask",  # type: ignore[call-arg]
            another_custom={"pattern": "allow"},  # type: ignore[call-arg]
        )
        assert perm.read == "allow"
        # Extra fields should be accessible via model_dump
        dumped = perm.model_dump()
        assert dumped["custom_mcp_tool"] == "ask"
        assert dumped["another_custom"] == {"pattern": "allow"}

    def test_permission_invalid_string_action_raises_validation_error(self) -> None:
        """Permission field rejects invalid string action."""
        from sage.config import Permission

        with pytest.raises(ValidationError):
            Permission(read="invalid")  # type: ignore[arg-type]

    def test_permission_dict_invalid_value_raises_validation_error(self) -> None:
        """Permission field dict with invalid action value raises ValidationError."""
        from sage.config import Permission

        with pytest.raises(ValidationError):
            Permission(shell={"*": "invalid_action"})  # type: ignore[arg-type]

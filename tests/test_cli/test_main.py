"""Tests for Sage CLI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from sage.cli.main import _resolve_primary_agent, cli
from sage.exceptions import ConfigError
from sage.main_config import MainConfig
from sage.permissions.allow_all import AllowAllPermissionHandler


def _write_valid_config(tmp_path: Path) -> Path:
    """Write a minimal valid agent config and return its path."""
    config = tmp_path / "AGENTS.md"
    config.write_text(
        "---\n"
        "name: test-agent\n"
        "model: gpt-4o\n"
        "extensions:\n"
        "  - my_tools.search\n"
        "  - my_tools.calc\n"
        "max_turns: 5\n"
        "---\n\n"
        "A helpful assistant.\n"
    )
    return config


def _write_config_with_subagents(tmp_path: Path) -> Path:
    """Write a config with subagents and return its path."""
    config = tmp_path / "AGENTS.md"
    config.write_text(
        "---\n"
        "name: orchestrator\n"
        "model: gpt-4o\n"
        "subagents:\n"
        "  - name: researcher\n"
        "    model: gpt-4o-mini\n"
        "---\n\n"
        "An orchestrator.\n"
    )
    return config


def _write_config_with_mcp(tmp_path: Path) -> Path:
    """Write a config with MCP servers and return its path."""
    config = tmp_path / "AGENTS.md"
    config.write_text(
        "---\n"
        "name: mcp-agent\n"
        "model: gpt-4o\n"
        "mcp_servers:\n"
        "  my-stdio:\n"
        "    transport: stdio\n"
        "    command: my-mcp-server\n"
        "  my-sse:\n"
        "    transport: sse\n"
        "    url: http://localhost:3000\n"
        "---\n\n"
        "An agent.\n"
    )
    return config


class TestAgentValidate:
    def test_valid_config(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "validate", str(config_path)])
        assert result.exit_code == 0
        assert "Config valid: test-agent (model: gpt-4o)" in result.output
        assert "Extensions: my_tools.search, my_tools.calc" in result.output

    def test_valid_config_with_subagents(self, tmp_path: Path) -> None:
        config_path = _write_config_with_subagents(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "validate", str(config_path)])
        assert result.exit_code == 0
        assert "Config valid: orchestrator" in result.output
        assert "Subagents: researcher" in result.output

    def test_valid_config_with_mcp(self, tmp_path: Path) -> None:
        config_path = _write_config_with_mcp(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "validate", str(config_path)])
        assert result.exit_code == 0
        assert "MCP servers: 2" in result.output

    def test_invalid_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "bad.md"
        config_path.write_text("not: valid: yaml: [")
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "validate", str(config_path)])
        assert result.exit_code != 0
        assert "Invalid config" in result.output

    def test_missing_required_fields(self, tmp_path: Path) -> None:
        config_path = tmp_path / "incomplete.md"
        config_path.write_text("---\nmax_turns: 10\n---\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "validate", str(config_path)])
        assert result.exit_code != 0
        assert "Invalid config" in result.output


class TestAgentList:
    def test_list_configs(self, tmp_path: Path) -> None:
        _write_valid_config(tmp_path)
        (tmp_path / "other.md").write_text(
            "---\nname: other-agent\nmodel: claude-3\n---\n\nAnother.\n"
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "list", str(tmp_path)])
        assert result.exit_code == 0
        assert "test-agent" in result.output
        assert "other-agent" in result.output

    def test_list_empty(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "list", str(tmp_path)])
        assert result.exit_code == 0
        assert "No agent config files found." in result.output

    def test_list_with_invalid_config(self, tmp_path: Path) -> None:
        (tmp_path / "broken.md").write_text("not a valid config")
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "list", str(tmp_path)])
        assert result.exit_code == 0
        assert "[invalid config]" in result.output


class TestToolList:
    def test_list_tools(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["tool", "list", str(config_path)])
        assert result.exit_code == 0
        assert "Extensions:" in result.output
        assert "- my_tools.search" in result.output
        assert "- my_tools.calc" in result.output

    def test_list_no_tools(self, tmp_path: Path) -> None:
        config_path = tmp_path / "no_tools.md"
        config_path.write_text("---\nname: bare\nmodel: gpt-4o\n---\n\nBare.\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["tool", "list", str(config_path)])
        assert result.exit_code == 0
        # bare config has no explicit extensions but inherits permission from main config
        assert "Tools for bare:" in result.output or "No tools configured." in result.output


class TestInit:
    def test_creates_files(self, tmp_path: Path, monkeypatch: object) -> None:
        monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--name", "demo", "--model", "claude-3"])
        assert result.exit_code == 0
        assert "Created AGENTS.md" in result.output

        md_path = tmp_path / "AGENTS.md"
        assert md_path.exists()

        md_content = md_path.read_text()
        assert "name: demo" in md_content
        assert "model: claude-3" in md_content
        assert "You are demo" in md_content
        assert "tools:" not in md_content  # tools field should not exist

    def test_creates_with_defaults(self, tmp_path: Path, monkeypatch: object) -> None:
        monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
        runner = CliRunner()
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0

        md_content = (tmp_path / "AGENTS.md").read_text()
        assert "name: my-agent" in md_content
        assert "model: gpt-4o" in md_content

    def test_existing_aborts(self, tmp_path: Path, monkeypatch: object) -> None:
        monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
        (tmp_path / "AGENTS.md").write_text("existing")
        runner = CliRunner()
        result = runner.invoke(cli, ["init"])
        assert result.exit_code != 0
        assert "already exists" in result.output


class TestResolvePrimaryAgent:
    def test_none_main_config_raises(self) -> None:
        with pytest.raises(ConfigError, match="No config.toml found"):
            _resolve_primary_agent(None)

    def test_primary_flat_md(self, tmp_path: Path, monkeypatch: object) -> None:
        monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "orchestrator.md").write_text("---\nname: orchestrator\n---\n")
        mc = MainConfig(agents_dir="agents/", primary="orchestrator")
        assert _resolve_primary_agent(mc) == "agents/orchestrator.md"

    def test_primary_subdirectory(self, tmp_path: Path, monkeypatch: object) -> None:
        monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
        agents_dir = tmp_path / "agents"
        sub = agents_dir / "orchestrator"
        sub.mkdir(parents=True)
        (sub / "AGENTS.md").write_text("---\nname: orchestrator\n---\n")
        mc = MainConfig(agents_dir="agents/", primary="orchestrator")
        assert _resolve_primary_agent(mc) == "agents/orchestrator/AGENTS.md"

    def test_primary_not_found_raises(self, tmp_path: Path, monkeypatch: object) -> None:
        monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
        (tmp_path / "agents").mkdir()
        mc = MainConfig(agents_dir="agents/", primary="missing")
        with pytest.raises(ConfigError, match="Primary agent 'missing' not found"):
            _resolve_primary_agent(mc)

    def test_no_primary_fallback_agents_md(self, tmp_path: Path, monkeypatch: object) -> None:
        monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "AGENTS.md").write_text("---\nname: default\n---\n")
        mc = MainConfig(agents_dir="agents/")
        assert _resolve_primary_agent(mc) == "agents/AGENTS.md"

    def test_no_primary_no_agents_md_raises(self, tmp_path: Path, monkeypatch: object) -> None:
        monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
        (tmp_path / "agents").mkdir()
        mc = MainConfig(agents_dir="agents/")
        with pytest.raises(ConfigError, match="No 'primary' set"):
            _resolve_primary_agent(mc)


class TestAgentRun:
    def test_run_basic(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Hello from the agent!")
        mock_agent.close = AsyncMock()
        mock_agent.tool_registry = MagicMock()
        mock_agent.tool_registry.set_permission_handler = MagicMock()
        mock_agent.subagents = {}

        mock_cls = MagicMock()
        mock_cls.from_config.return_value = mock_agent

        with patch.dict(
            "sys.modules",
            {"sage.agent": MagicMock(Agent=mock_cls)},
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["agent", "run", str(config_path), "-i", "Hello"],
            )
            assert result.exit_code == 0
            assert "Hello from the agent!" in result.output

    def test_run_stream(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        mock_agent = MagicMock()
        mock_agent.close = AsyncMock()
        mock_agent.tool_registry = MagicMock()
        mock_agent.tool_registry.set_permission_handler = MagicMock()
        mock_agent.subagents = {}

        async def mock_stream(input: str):  # noqa: A002
            for chunk in ["Hello", " from", " stream!"]:
                yield chunk

        mock_agent.stream = mock_stream

        mock_cls = MagicMock()
        mock_cls.from_config.return_value = mock_agent

        with patch.dict(
            "sys.modules",
            {"sage.agent": MagicMock(Agent=mock_cls)},
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["agent", "run", str(config_path), "-i", "Hello", "--stream"],
            )
            assert result.exit_code == 0
            assert "Hello from stream!" in result.output

    def test_run_error(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)

        from sage.exceptions import SageError

        mock_cls = MagicMock()
        mock_cls.from_config.side_effect = SageError("Provider unavailable")

        with patch.dict(
            "sys.modules",
            {"sage.agent": MagicMock(Agent=mock_cls)},
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["agent", "run", str(config_path), "-i", "Hello"],
            )
            assert result.exit_code != 0
            assert "Error" in result.output

    def test_run_with_directory(self, tmp_path: Path) -> None:
        """agent run accepts a directory containing AGENTS.md."""
        _write_valid_config(tmp_path)  # creates tmp_path/AGENTS.md
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Hello from dir!")
        mock_agent.close = AsyncMock()
        mock_agent.tool_registry = MagicMock()
        mock_agent.tool_registry.set_permission_handler = MagicMock()
        mock_agent.subagents = {}

        mock_cls = MagicMock()
        mock_cls.from_config.return_value = mock_agent

        with patch.dict(
            "sys.modules",
            {"sage.agent": MagicMock(Agent=mock_cls)},
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["agent", "run", str(tmp_path), "-i", "Hello"],
            )
            assert result.exit_code == 0
            assert "Hello from dir!" in result.output

    def test_run_infers_primary_from_config(self, tmp_path: Path, monkeypatch: object) -> None:
        """agent run without config_path resolves primary from config.toml."""
        monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        agent_file = agents_dir / "my-agent.md"
        agent_file.write_text("---\nname: my-agent\nmodel: gpt-4o\n---\n\nHello.\n")

        # Write config.toml
        config_toml = tmp_path / "config.toml"
        config_toml.write_text('agents_dir = "agents/"\nprimary = "my-agent"\n')

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Inferred!")
        mock_agent.close = AsyncMock()
        mock_agent.tool_registry = MagicMock()
        mock_agent.tool_registry.set_permission_handler = MagicMock()
        mock_agent.subagents = {}

        mock_cls = MagicMock()
        mock_cls.from_config.return_value = mock_agent

        with patch.dict(
            "sys.modules",
            {"sage.agent": MagicMock(Agent=mock_cls)},
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["--config", str(config_toml), "agent", "run", "-i", "Hello"],
            )
            assert result.exit_code == 0
            assert "Inferred!" in result.output

    def test_run_with_yolo_installs_allow_all_permission_handler(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Hello from the agent!")
        mock_agent.close = AsyncMock()
        mock_agent.tool_registry = MagicMock()
        mock_agent.tool_registry.set_permission_handler = MagicMock()
        mock_agent.subagents = {}

        mock_cls = MagicMock()
        mock_cls.from_config.return_value = mock_agent

        with patch.dict(
            "sys.modules",
            {"sage.agent": MagicMock(Agent=mock_cls)},
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["--yolo", "agent", "run", str(config_path), "-i", "Hello"],
            )

        assert result.exit_code == 0, result.output
        mock_agent.tool_registry.set_permission_handler.assert_called_once()
        handler = mock_agent.tool_registry.set_permission_handler.call_args.args[0]
        assert isinstance(handler, AllowAllPermissionHandler)

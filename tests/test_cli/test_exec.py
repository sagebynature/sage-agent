"""Tests for the ``sage exec`` CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from sage.cli.main import cli
from sage.permissions.allow_all import AllowAllPermissionHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_valid_config(tmp_path: Path) -> Path:
    config = tmp_path / "AGENTS.md"
    config.write_text(
        "---\nname: test-agent\nmodel: gpt-4o\nmax_turns: 5\n---\n\nA helpful assistant.\n"
    )
    return config


def _make_mock_agent(return_value: str = "Agent result") -> tuple[MagicMock, MagicMock]:
    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=return_value)
    mock_agent.close = AsyncMock()
    mock_agent.tool_registry = MagicMock()
    mock_agent.tool_registry.set_ask_policy = MagicMock()
    mock_agent.tool_registry.set_permission_handler = MagicMock()
    mock_agent.subagents = {}

    mock_cls = MagicMock()
    mock_cls.from_config.return_value = mock_agent
    return mock_agent, mock_cls


# ---------------------------------------------------------------------------
# Output mode tests
# ---------------------------------------------------------------------------


class TestExecOutputMode:
    def test_text_mode_default(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        mock_agent, mock_cls = _make_mock_agent("Hello, world!")

        with patch.dict("sys.modules", {"sage.agent": MagicMock(Agent=mock_cls)}):
            runner = CliRunner()
            result = runner.invoke(cli, ["exec", str(config_path), "-i", "Hi"])

        assert result.exit_code == 0, result.output
        assert "Hello, world!" in result.output

    def test_jsonl_mode(self, tmp_path: Path) -> None:
        import json

        config_path = _write_valid_config(tmp_path)
        mock_agent, mock_cls = _make_mock_agent("JSONL result")

        with patch.dict("sys.modules", {"sage.agent": MagicMock(Agent=mock_cls)}):
            runner = CliRunner()
            result = runner.invoke(cli, ["exec", str(config_path), "-i", "Hi", "--output", "jsonl"])

        assert result.exit_code == 0, result.output
        lines = [line for line in result.output.splitlines() if line.strip()]
        assert lines, "No output lines produced"
        last = json.loads(lines[-1])
        assert last["event"] == "result"
        assert last["data"]["output"] == "JSONL result"

    def test_quiet_mode_suppresses_output(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        mock_agent, mock_cls = _make_mock_agent("Quiet result")

        with patch.dict("sys.modules", {"sage.agent": MagicMock(Agent=mock_cls)}):
            runner = CliRunner()
            result = runner.invoke(cli, ["exec", str(config_path), "-i", "Hi", "--output", "quiet"])

        assert result.exit_code == 0, result.output
        # Result should NOT appear in output
        assert "Quiet result" not in result.output


# ---------------------------------------------------------------------------
# Exit code tests
# ---------------------------------------------------------------------------


class TestExecExitCodes:
    def test_exit_0_on_success(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        mock_agent, mock_cls = _make_mock_agent()

        with patch.dict("sys.modules", {"sage.agent": MagicMock(Agent=mock_cls)}):
            runner = CliRunner()
            result = runner.invoke(cli, ["exec", str(config_path), "-i", "Hi"])

        assert result.exit_code == 0

    def test_exit_2_on_config_error(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        from sage.exceptions import ConfigError

        mock_cls = MagicMock()
        mock_cls.from_config.side_effect = ConfigError("bad config")

        with patch.dict("sys.modules", {"sage.agent": MagicMock(Agent=mock_cls)}):
            runner = CliRunner()
            result = runner.invoke(cli, ["exec", str(config_path), "-i", "Hi"])

        assert result.exit_code == 2

    def test_exit_3_on_permission_denied(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        from sage.exceptions import PermissionError as SagePermissionError

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=SagePermissionError("denied"))
        mock_agent.close = AsyncMock()
        mock_agent.tool_registry = MagicMock()
        mock_agent.tool_registry.set_ask_policy = MagicMock()

        mock_cls = MagicMock()
        mock_cls.from_config.return_value = mock_agent

        with patch.dict("sys.modules", {"sage.agent": MagicMock(Agent=mock_cls)}):
            runner = CliRunner()
            result = runner.invoke(cli, ["exec", str(config_path), "-i", "Hi"])

        assert result.exit_code == 3

    def test_exit_6_on_tool_error(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        from sage.exceptions import ToolError

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=ToolError("tool broke"))
        mock_agent.close = AsyncMock()
        mock_agent.tool_registry = MagicMock()
        mock_agent.tool_registry.set_ask_policy = MagicMock()

        mock_cls = MagicMock()
        mock_cls.from_config.return_value = mock_agent

        with patch.dict("sys.modules", {"sage.agent": MagicMock(Agent=mock_cls)}):
            runner = CliRunner()
            result = runner.invoke(cli, ["exec", str(config_path), "-i", "Hi"])

        assert result.exit_code == 6

    def test_exit_7_on_provider_error(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        from sage.exceptions import ProviderError

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=ProviderError("provider down"))
        mock_agent.close = AsyncMock()
        mock_agent.tool_registry = MagicMock()
        mock_agent.tool_registry.set_ask_policy = MagicMock()

        mock_cls = MagicMock()
        mock_cls.from_config.return_value = mock_agent

        with patch.dict("sys.modules", {"sage.agent": MagicMock(Agent=mock_cls)}):
            runner = CliRunner()
            result = runner.invoke(cli, ["exec", str(config_path), "-i", "Hi"])

        assert result.exit_code == 7

    def test_exit_1_on_no_input(self, tmp_path: Path) -> None:
        """Missing input should exit 1."""
        config_path = _write_valid_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["exec", str(config_path)])
        assert result.exit_code == 1

    def test_exit_1_on_generic_sage_error(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        from sage.exceptions import SageError

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=SageError("generic"))
        mock_agent.close = AsyncMock()
        mock_agent.tool_registry = MagicMock()
        mock_agent.tool_registry.set_ask_policy = MagicMock()

        mock_cls = MagicMock()
        mock_cls.from_config.return_value = mock_agent

        with patch.dict("sys.modules", {"sage.agent": MagicMock(Agent=mock_cls)}):
            runner = CliRunner()
            result = runner.invoke(cli, ["exec", str(config_path), "-i", "Hi"])

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Ask policy tests
# ---------------------------------------------------------------------------


class TestExecAskPolicy:
    def test_default_deny_all(self, tmp_path: Path) -> None:
        """Default sage exec behaviour: deny all ASK-gated calls."""
        config_path = _write_valid_config(tmp_path)
        mock_agent, mock_cls = _make_mock_agent()

        with patch.dict("sys.modules", {"sage.agent": MagicMock(Agent=mock_cls)}):
            runner = CliRunner()
            runner.invoke(cli, ["exec", str(config_path), "-i", "Hi"])

        mock_agent.tool_registry.set_ask_policy.assert_called_once_with("deny")

    def test_yes_flag_sets_allow(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        mock_agent, mock_cls = _make_mock_agent()

        with patch.dict("sys.modules", {"sage.agent": MagicMock(Agent=mock_cls)}):
            runner = CliRunner()
            runner.invoke(cli, ["exec", str(config_path), "-i", "Hi", "--yes"])

        mock_agent.tool_registry.set_ask_policy.assert_called_once_with("allow")

    def test_yolo_flag_installs_allow_all_permission_handler(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        mock_agent, mock_cls = _make_mock_agent()

        with patch.dict("sys.modules", {"sage.agent": MagicMock(Agent=mock_cls)}):
            runner = CliRunner()
            result = runner.invoke(cli, ["--yolo", "exec", str(config_path), "-i", "Hi"])

        assert result.exit_code == 0, result.output
        mock_agent.tool_registry.set_permission_handler.assert_called_once()
        handler = mock_agent.tool_registry.set_permission_handler.call_args.args[0]
        assert isinstance(handler, AllowAllPermissionHandler)

    def test_short_yolo_flag_installs_allow_all_permission_handler(self, tmp_path: Path) -> None:
        config_path = _write_valid_config(tmp_path)
        mock_agent, mock_cls = _make_mock_agent()

        with patch.dict("sys.modules", {"sage.agent": MagicMock(Agent=mock_cls)}):
            runner = CliRunner()
            result = runner.invoke(cli, ["exec", str(config_path), "-i", "Hi", "-y"])

        assert result.exit_code == 0, result.output
        mock_agent.tool_registry.set_permission_handler.assert_called_once()
        handler = mock_agent.tool_registry.set_permission_handler.call_args.args[0]
        assert isinstance(handler, AllowAllPermissionHandler)

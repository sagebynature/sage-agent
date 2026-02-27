"""Tests for SandboxConfig parsing and validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from sage.config import SandboxConfig


class TestSandboxConfigDefaults:
    """Verify default field values."""

    def test_backend_default(self) -> None:
        config = SandboxConfig()
        assert config.backend == "native"

    def test_enabled_default_false(self) -> None:
        """enabled must default to False (opt-in, never break existing users)."""
        config = SandboxConfig()
        assert config.enabled is False

    def test_network_default_true(self) -> None:
        config = SandboxConfig()
        assert config.network is True

    def test_timeout_default(self) -> None:
        config = SandboxConfig()
        assert config.timeout == 30.0

    def test_mode_default(self) -> None:
        config = SandboxConfig()
        assert config.mode == "workspace-write"

    def test_deny_read_contains_ssh(self) -> None:
        config = SandboxConfig()
        assert "~/.ssh" in config.deny_read

    def test_deny_read_contains_aws(self) -> None:
        config = SandboxConfig()
        assert "~/.aws" in config.deny_read

    def test_deny_read_contains_gnupg(self) -> None:
        config = SandboxConfig()
        assert "~/.gnupg" in config.deny_read

    def test_writable_roots_default(self) -> None:
        config = SandboxConfig()
        assert "/tmp" in config.writable_roots

    def test_allowed_env_default_empty(self) -> None:
        config = SandboxConfig()
        assert config.allowed_env == []


class TestSandboxConfigValidBackends:
    """All literal backend values must be accepted."""

    @pytest.mark.parametrize(
        "backend",
        ["auto", "native", "bubblewrap", "seatbelt", "docker", "none"],
    )
    def test_valid_backend(self, backend: str) -> None:
        config = SandboxConfig(backend=backend)
        assert config.backend == backend


class TestSandboxConfigInvalidBackend:
    def test_invalid_backend_raises(self) -> None:
        with pytest.raises(ValidationError):
            SandboxConfig(backend="invalid")


class TestSandboxConfigCustomValues:
    def test_enabled_true(self) -> None:
        config = SandboxConfig(enabled=True)
        assert config.enabled is True

    def test_workspace_as_path(self) -> None:
        config = SandboxConfig(workspace=Path("/tmp/workspace"))
        assert config.workspace == Path("/tmp/workspace")

    def test_workspace_as_string_coerced(self) -> None:
        config = SandboxConfig(workspace="/tmp/workspace")
        assert config.workspace == Path("/tmp/workspace")

    def test_network_false(self) -> None:
        config = SandboxConfig(network=False)
        assert config.network is False

    def test_timeout_custom(self) -> None:
        config = SandboxConfig(timeout=60.0)
        assert config.timeout == 60.0

    def test_mode_read_only(self) -> None:
        config = SandboxConfig(mode="read-only")
        assert config.mode == "read-only"

    def test_mode_full_access(self) -> None:
        config = SandboxConfig(mode="full-access")
        assert config.mode == "full-access"

    def test_deny_read_custom(self) -> None:
        config = SandboxConfig(deny_read=["~/.config"])
        assert "~/.config" in config.deny_read

    def test_writable_roots_custom(self) -> None:
        config = SandboxConfig(writable_roots=["/tmp", "/var/tmp"])
        assert "/var/tmp" in config.writable_roots

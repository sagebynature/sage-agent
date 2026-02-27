"""Tests for SeatbeltSandbox (macOS only)."""

from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import patch

import pytest

from sage.exceptions import ToolError

pytestmark = pytest.mark.skipif(platform.system() != "Darwin", reason="requires macOS")


class TestSeatbeltInstantiation:
    def test_raises_when_sandbox_exec_not_found(self) -> None:
        """If sandbox-exec is not on PATH, instantiation must raise ToolError."""
        with patch("shutil.which", return_value=None):
            from sage.tools._sandbox import SeatbeltSandbox

            with pytest.raises(ToolError, match="sandbox-exec"):
                SeatbeltSandbox()

    def test_instantiates_when_sandbox_exec_found(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/sandbox-exec"):
            from sage.tools._sandbox import SeatbeltSandbox

            sandbox = SeatbeltSandbox()
            assert sandbox is not None


class TestSeatbeltProfile:
    """Verify the generated Seatbelt profile content."""

    def test_profile_denies_root_writes(self, tmp_path: Path) -> None:
        """Profile must deny writes to /."""
        with patch("shutil.which", return_value="/usr/bin/sandbox-exec"):
            from sage.tools._sandbox import SeatbeltSandbox

            sandbox = SeatbeltSandbox(workspace=tmp_path)
            profile = sandbox._generate_profile()

        assert '(deny file-write* (subpath "/"))' in profile

    def test_profile_allows_workspace_writes(self, tmp_path: Path) -> None:
        """Profile must allow writes within the workspace directory."""
        with patch("shutil.which", return_value="/usr/bin/sandbox-exec"):
            from sage.tools._sandbox import SeatbeltSandbox

            sandbox = SeatbeltSandbox(workspace=tmp_path)
            profile = sandbox._generate_profile()

        workspace_str = str(tmp_path.resolve())
        assert workspace_str in profile
        assert f'(allow file-write* (subpath "{workspace_str}"))' in profile

    def test_profile_network_false_denies_network(self, tmp_path: Path) -> None:
        """When network=False the profile must contain (deny network*)."""
        with patch("shutil.which", return_value="/usr/bin/sandbox-exec"):
            from sage.tools._sandbox import SeatbeltSandbox

            sandbox = SeatbeltSandbox(network=False, workspace=tmp_path)
            profile = sandbox._generate_profile()

        assert "(deny network*)" in profile

    def test_profile_network_true_no_deny_network(self, tmp_path: Path) -> None:
        """When network=True (default) the profile must NOT deny network."""
        with patch("shutil.which", return_value="/usr/bin/sandbox-exec"):
            from sage.tools._sandbox import SeatbeltSandbox

            sandbox = SeatbeltSandbox(network=True, workspace=tmp_path)
            profile = sandbox._generate_profile()

        assert "(deny network*)" not in profile

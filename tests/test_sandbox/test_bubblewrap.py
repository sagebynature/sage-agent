"""Tests for BubblewrapSandbox (Linux only)."""

from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sage.exceptions import ToolError

pytestmark = pytest.mark.skipif(platform.system() != "Linux", reason="requires Linux")


class TestBubblewrapInstantiation:
    def test_raises_when_bwrap_not_found(self) -> None:
        """If bwrap is not on PATH, instantiation must raise ToolError."""
        with patch("shutil.which", return_value=None):
            from sage.tools._sandbox import BubblewrapSandbox

            with pytest.raises(ToolError, match="bwrap"):
                BubblewrapSandbox()

    def test_instantiates_when_bwrap_found(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/bwrap"):
            from sage.tools._sandbox import BubblewrapSandbox

            sandbox = BubblewrapSandbox()
            assert sandbox is not None


class TestBubblewrapExecuteArgs:
    """Verify the bwrap command arguments are constructed correctly."""

    def _make_proc(self) -> MagicMock:
        proc = MagicMock()
        proc.communicate = AsyncMock(return_value=(b"stdout\n", b""))
        proc.kill = MagicMock()
        return proc

    async def test_ro_bind_root_present(self, tmp_path: Path) -> None:
        """--ro-bind / / must appear in bwrap args."""
        captured_args: list[str] = []

        async def fake_exec(*args: str, **kwargs: object) -> MagicMock:
            captured_args.extend(args)
            return self._make_proc()

        with (
            patch("shutil.which", return_value="/usr/bin/bwrap"),
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_exec,
            ),
        ):
            from sage.tools._sandbox import BubblewrapSandbox

            sandbox = BubblewrapSandbox(workspace=tmp_path)
            await sandbox.execute("echo test")

        # Check --ro-bind / / sequence
        for i in range(len(captured_args) - 2):
            if (
                captured_args[i] == "--ro-bind"
                and captured_args[i + 1] == "/"
                and captured_args[i + 2] == "/"
            ):
                break
        else:
            pytest.fail("--ro-bind / / not found in bwrap args")

    async def test_clearenv_present(self, tmp_path: Path) -> None:
        """--clearenv must appear in bwrap args."""
        captured_args: list[str] = []

        async def fake_exec(*args: str, **kwargs: object) -> MagicMock:
            captured_args.extend(args)
            return self._make_proc()

        with (
            patch("shutil.which", return_value="/usr/bin/bwrap"),
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_exec,
            ),
        ):
            from sage.tools._sandbox import BubblewrapSandbox

            sandbox = BubblewrapSandbox(workspace=tmp_path)
            await sandbox.execute("echo test")

        assert "--clearenv" in captured_args

    async def test_unshare_net_when_network_false(self, tmp_path: Path) -> None:
        """--unshare-net must appear when network=False."""
        captured_args: list[str] = []

        async def fake_exec(*args: str, **kwargs: object) -> MagicMock:
            captured_args.extend(args)
            return self._make_proc()

        with (
            patch("shutil.which", return_value="/usr/bin/bwrap"),
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_exec,
            ),
        ):
            from sage.tools._sandbox import BubblewrapSandbox

            sandbox = BubblewrapSandbox(network=False, workspace=tmp_path)
            await sandbox.execute("echo test")

        assert "--unshare-net" in captured_args

    async def test_no_unshare_net_when_network_true(self, tmp_path: Path) -> None:
        """--unshare-net must NOT appear when network=True (default)."""
        captured_args: list[str] = []

        async def fake_exec(*args: str, **kwargs: object) -> MagicMock:
            captured_args.extend(args)
            return self._make_proc()

        with (
            patch("shutil.which", return_value="/usr/bin/bwrap"),
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_exec,
            ),
        ):
            from sage.tools._sandbox import BubblewrapSandbox

            sandbox = BubblewrapSandbox(network=True, workspace=tmp_path)
            await sandbox.execute("echo test")

        assert "--unshare-net" not in captured_args

    async def test_deny_read_existing_path_adds_tmpfs(self, tmp_path: Path) -> None:
        """Existing deny_read paths should be masked with --tmpfs."""
        # Create a real path to deny
        sensitive = tmp_path / "sensitive"
        sensitive.mkdir()
        captured_args: list[str] = []

        async def fake_exec(*args: str, **kwargs: object) -> MagicMock:
            captured_args.extend(args)
            return self._make_proc()

        with (
            patch("shutil.which", return_value="/usr/bin/bwrap"),
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_exec,
            ),
        ):
            from sage.tools._sandbox import BubblewrapSandbox

            sandbox = BubblewrapSandbox(
                workspace=tmp_path,
                deny_read=[str(sensitive)],
            )
            await sandbox.execute("echo test")

        assert "--tmpfs" in captured_args

    async def test_deny_read_nonexistent_path_skipped(self, tmp_path: Path) -> None:
        """Non-existent deny_read paths must NOT add --tmpfs entries."""
        captured_args: list[str] = []

        async def fake_exec(*args: str, **kwargs: object) -> MagicMock:
            captured_args.extend(args)
            return self._make_proc()

        with (
            patch("shutil.which", return_value="/usr/bin/bwrap"),
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=fake_exec,
            ),
        ):
            from sage.tools._sandbox import BubblewrapSandbox

            sandbox = BubblewrapSandbox(
                workspace=tmp_path,
                deny_read=[str(tmp_path / "does_not_exist")],
            )
            await sandbox.execute("echo test")

        assert "--tmpfs" not in captured_args

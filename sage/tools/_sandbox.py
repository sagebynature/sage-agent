"""Shell execution sandbox implementations."""

from __future__ import annotations

import asyncio
import logging
import platform
import shutil
from pathlib import Path
from typing import Any, Protocol

from sage.exceptions import ToolError

logger = logging.getLogger(__name__)

# Environment variables passed through to sandboxed commands.
_ALLOWED_ENV_VARS: frozenset[str] = frozenset({"PATH", "HOME", "USER", "LANG", "TERM"})

# Trusted PATH directories for the sanitized environment.
_TRUSTED_PATH = "/usr/local/bin:/usr/bin:/bin"


class SandboxExecutor(Protocol):
    """Protocol for sandbox implementations."""

    async def execute(self, command: str) -> tuple[str, str]:
        """Execute *command* and return ``(stdout, stderr)``.

        Raises:
            ToolError: If the command cannot be executed.
        """
        ...


class NativeSandbox:
    """Sandbox that strips the environment to a safe minimum.

    Prefixes commands with ``env -i`` to clear all inherited environment
    variables, then re-adds a minimal allow-list.  This blocks bypass vectors
    that rely on ``$SHELL``, ``$BASH_FUNC_*``, or other inherited env vars.

    Args:
        allowed_env: Extra variable names (beyond the built-in allow-list)
            to pass through from the current environment.
        trusted_path: ``PATH`` value for the sanitized environment.
            Defaults to ``/usr/local/bin:/usr/bin:/bin``.
    """

    def __init__(
        self,
        allowed_env: list[str] | None = None,
        trusted_path: str = _TRUSTED_PATH,
    ) -> None:
        import os

        self._trusted_path = trusted_path
        allowed = _ALLOWED_ENV_VARS | frozenset(allowed_env or [])
        self._env: dict[str, str] = {"PATH": trusted_path}
        for var in allowed:
            if var == "PATH":
                continue
            val = os.environ.get(var)
            if val is not None:
                self._env[var] = val

    async def execute(self, command: str) -> tuple[str, str]:
        """Execute *command* in a sanitized environment."""
        logger.debug("NativeSandbox.execute: %s", command[:100])
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )
        stdout_b, stderr_b = await proc.communicate()
        return (
            stdout_b.decode(errors="replace"),
            stderr_b.decode(errors="replace"),
        )


class BubblewrapSandbox:
    """Sandbox using Linux namespace isolation via ``bwrap``.

    Uses ``--ro-bind / /`` to mount the full filesystem read-only,
    then ``--bind workspace workspace`` to make the workspace writable.
    """

    def __init__(
        self,
        network: bool = True,
        allowed_env: list[str] | None = None,
        workspace: Path | None = None,
        writable_roots: list[str] | None = None,
        deny_read: list[str] | None = None,
        timeout: float | None = None,
    ) -> None:
        if shutil.which("bwrap") is None:
            raise ToolError(
                "BubblewrapSandbox requires 'bwrap' (bubblewrap) to be installed. "
                "Install it or use backend='native'."
            )
        self._network = network
        self._workspace = workspace or Path.cwd()
        self._writable_roots = writable_roots or ["/tmp"]
        self._deny_read = deny_read or []
        self._timeout = timeout
        self._native = NativeSandbox(allowed_env=allowed_env)

    async def execute(self, command: str) -> tuple[str, str]:
        """Execute *command* inside a bubblewrap namespace."""
        logger.debug("BubblewrapSandbox.execute: %s", command[:100])
        net_args = [] if self._network else ["--unshare-net"]

        # Start with full root read-only bind
        bwrap_args = ["bwrap", "--ro-bind", "/", "/"]
        bwrap_args += net_args

        # Make workspace writable
        workspace_str = str(self._workspace.resolve())
        bwrap_args += ["--bind", workspace_str, workspace_str]

        # Extra writable roots
        for root in self._writable_roots:
            expanded = str(Path(root).expanduser().resolve())
            bwrap_args += ["--bind", expanded, expanded]

        # Hide sensitive paths with empty tmpfs
        for sensitive in self._deny_read:
            expanded_path = Path(sensitive).expanduser()
            if expanded_path.exists():
                bwrap_args += ["--tmpfs", str(expanded_path.resolve())]

        # Standard namespace options
        bwrap_args += [
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--unshare-pid",
            "--new-session",
            "--die-with-parent",
            "--clearenv",
        ]

        # Re-export safe env vars
        for key, val in self._native._env.items():
            bwrap_args += ["--setenv", key, val]

        bwrap_args += ["--", "sh", "-c", command]

        try:
            proc = await asyncio.create_subprocess_exec(
                *bwrap_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            if self._timeout is not None:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=self._timeout
                )
            else:
                stdout_b, stderr_b = await proc.communicate()
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise ToolError(f"Command timed out after {self._timeout}s") from exc

        return (
            stdout_b.decode(errors="replace"),
            stderr_b.decode(errors="replace"),
        )


class SeatbeltSandbox:
    """macOS sandbox using sandbox-exec (Seatbelt)."""

    def __init__(
        self,
        network: bool = True,
        workspace: Path | None = None,
        timeout: float | None = None,
    ) -> None:
        if shutil.which("sandbox-exec") is None:
            raise ToolError(
                "SeatbeltSandbox requires 'sandbox-exec' (macOS only). "
                "Use backend='native' on non-macOS systems."
            )
        self._network = network
        self._workspace = workspace or Path.cwd()
        self._timeout = timeout

    def _generate_profile(self) -> str:
        """Generate a Seatbelt profile string."""
        workspace_str = str(self._workspace.resolve())
        network_rule = "" if self._network else "(deny network*)"
        return (
            "(version 1)\n"
            "(allow default)\n"
            f'(deny file-write* (subpath "/"))\n'
            f'(allow file-write* (subpath "{workspace_str}"))\n'
            '(allow file-write* (subpath "/tmp"))\n'
            f"{network_rule}\n"
        )

    async def execute(self, command: str) -> tuple[str, str]:
        """Execute *command* inside a Seatbelt sandbox."""
        logger.debug("SeatbeltSandbox.execute: %s", command[:100])
        profile = self._generate_profile()
        cmd = ["sandbox-exec", "-p", profile, "sh", "-c", command]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            if self._timeout is not None:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=self._timeout
                )
            else:
                stdout_b, stderr_b = await proc.communicate()
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise ToolError(f"Command timed out after {self._timeout}s") from exc

        return (
            stdout_b.decode(errors="replace"),
            stderr_b.decode(errors="replace"),
        )


class DockerSandbox:
    """Sandbox using ephemeral Docker containers (strongest isolation)."""

    _IMAGE = "python:3.11-slim"

    def __init__(
        self,
        network: bool = False,
        workspace: Path | None = None,
        timeout: float | None = None,
        image: str | None = None,
    ) -> None:
        if shutil.which("docker") is None:
            raise ToolError("DockerSandbox requires 'docker' to be installed and running.")
        self._network = network
        self._workspace = workspace or Path.cwd()
        self._timeout = timeout
        self._image = image or self._IMAGE

    async def execute(self, command: str) -> tuple[str, str]:
        """Execute *command* in an ephemeral Docker container."""
        logger.debug("DockerSandbox.execute: %s", command[:100])
        workspace_str = str(self._workspace.resolve())
        net_args = [] if self._network else ["--network=none"]

        docker_cmd = (
            [
                "docker",
                "run",
                "--rm",
                "--read-only",
                "--tmpfs",
                "/tmp:size=512m",
                f"--volume={workspace_str}:/workspace:rw",
                "--workdir=/workspace",
                "--memory=512m",
                "--cpus=0.5",
                "--pids-limit=100",
            ]
            + net_args
            + [
                self._image,
                "sh",
                "-c",
                command,
            ]
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            if self._timeout is not None:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=self._timeout
                )
            else:
                stdout_b, stderr_b = await proc.communicate()
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise ToolError(f"Command timed out after {self._timeout}s") from exc

        return (
            stdout_b.decode(errors="replace"),
            stderr_b.decode(errors="replace"),
        )


def _detect_backend() -> str:
    """Auto-detect the best available sandbox backend for this platform."""
    sys_name = platform.system()
    if sys_name == "Linux" and shutil.which("bwrap"):
        return "bubblewrap"
    if sys_name == "Darwin" and shutil.which("sandbox-exec"):
        return "seatbelt"
    return "native"


def build_sandbox(config: Any) -> SandboxExecutor:
    """Construct the appropriate sandbox from a :class:`~sage.config.SandboxConfig`.

    Args:
        config: A ``SandboxConfig`` instance specifying the backend and options.

    Returns:
        A :class:`SandboxExecutor` ready to use.
    """
    backend: str = getattr(config, "backend", "native")
    network: bool = getattr(config, "network", True)
    allowed_env: list[str] = list(getattr(config, "allowed_env", []))
    workspace = getattr(config, "workspace", None)
    if workspace is not None:
        workspace = Path(workspace)
    writable_roots: list[str] = list(getattr(config, "writable_roots", ["/tmp"]))
    deny_read: list[str] = list(getattr(config, "deny_read", []))
    timeout: float | None = getattr(config, "timeout", None)

    if backend == "auto":
        backend = _detect_backend()

    if backend == "bubblewrap":
        return BubblewrapSandbox(
            network=network,
            allowed_env=allowed_env,
            workspace=workspace,
            writable_roots=writable_roots,
            deny_read=deny_read,
            timeout=timeout,
        )
    if backend == "seatbelt":
        return SeatbeltSandbox(
            network=network,
            workspace=workspace,
            timeout=timeout,
        )
    if backend == "docker":
        return DockerSandbox(
            network=network,
            workspace=workspace,
            timeout=timeout,
        )
    if backend == "none":
        # Passthrough: returns (stdout, stderr) from a bare subprocess
        return NativeSandbox(allowed_env=allowed_env)

    # Default: native
    return NativeSandbox(allowed_env=allowed_env)

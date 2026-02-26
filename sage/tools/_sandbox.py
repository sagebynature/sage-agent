"""Shell execution sandbox implementations."""

from __future__ import annotations

import asyncio
import logging
import shutil
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

    Requires ``bwrap`` (bubblewrap) to be installed.  Falls back to raising
    ``ToolError`` if ``bwrap`` is not available.

    Args:
        network: Whether to allow network access inside the sandbox.
        allowed_env: Extra variable names to pass through.
    """

    def __init__(
        self,
        network: bool = True,
        allowed_env: list[str] | None = None,
    ) -> None:
        if shutil.which("bwrap") is None:
            raise ToolError(
                "BubblewrapSandbox requires 'bwrap' (bubblewrap) to be installed. "
                "Install it or use backend='native'."
            )
        self._network = network
        self._native = NativeSandbox(allowed_env=allowed_env)

    async def execute(self, command: str) -> tuple[str, str]:
        """Execute *command* inside a bubblewrap namespace."""
        logger.debug("BubblewrapSandbox.execute: %s", command[:100])
        net_args = [] if self._network else ["--unshare-net"]
        bwrap_cmd = (
            ["bwrap"]
            + net_args
            + [
                "--ro-bind",
                "/usr",
                "/usr",
                "--ro-bind",
                "/bin",
                "/bin",
                "--ro-bind",
                "/lib",
                "/lib",
                "--ro-bind-try",
                "/lib64",
                "/lib64",
                "--ro-bind-try",
                "/lib32",
                "/lib32",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--bind",
                "/tmp",
                "/tmp",
                "--bind",
                "/home",
                "/home",
                "--unshare-pid",
                "--die-with-parent",
                "--",
                "sh",
                "-c",
                command,
            ]
        )
        full_cmd = " ".join(bwrap_cmd)
        proc = await asyncio.create_subprocess_shell(
            full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._native._env,
        )
        stdout_b, stderr_b = await proc.communicate()
        return (
            stdout_b.decode(errors="replace"),
            stderr_b.decode(errors="replace"),
        )


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

    if backend == "bubblewrap":
        return BubblewrapSandbox(network=network, allowed_env=allowed_env)
    return NativeSandbox(allowed_env=allowed_env)

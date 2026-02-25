"""Main configuration loading, resolution, and merge for Sage.

Provides a TOML-based main config with a three-tier override system::

    agent .md frontmatter     (highest priority)
    [agents.<name>] in TOML   (agent-specific overrides)
    [defaults] in TOML         (global defaults)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from pydantic import BaseModel, ConfigDict, Field

from sage.config import (
    ContextConfig,
    MCPServerConfig,
    MemoryConfig,
    ModelParams,
    PermissionsConfig,
)
from sage.exceptions import ConfigError

logger = logging.getLogger(__name__)


class ConfigOverrides(BaseModel):
    """Fields that can appear in defaults or per-agent overrides."""

    model_config = ConfigDict(extra="forbid")

    model: str | None = None
    model_params: ModelParams | None = None
    max_turns: int | None = None
    permissions: PermissionsConfig | None = None
    context: ContextConfig | None = None
    tools: list[str] | None = None
    mcp_servers: list[MCPServerConfig] | None = None


class AgentOverrides(ConfigOverrides):
    """Per-agent overrides — adds memory and skills_dir."""

    memory: MemoryConfig | None = None
    skills_dir: str | None = None


class MainConfig(BaseModel):
    """Top-level main configuration loaded from config.toml."""

    model_config = ConfigDict(extra="forbid")

    defaults: ConfigOverrides = Field(default_factory=ConfigOverrides)
    agents: dict[str, AgentOverrides] = Field(default_factory=dict)


def resolve_main_config_path(cli_path: str | None = None) -> Path | None:
    """Resolve the main config file path.

    Priority: CLI ``--config`` arg -> ``SAGE_CONFIG_PATH`` env var -> default path.

    Explicit paths (CLI/env) that don't exist raise :class:`ConfigError`.
    Default path that doesn't exist returns ``None`` (backward compatible).
    """
    # 1. CLI argument
    if cli_path is not None:
        p = Path(cli_path)
        if not p.exists():
            raise ConfigError(f"Main config not found: {p}")
        return p

    # 2. Environment variable
    env_path = os.environ.get("SAGE_CONFIG_PATH")
    if env_path is not None:
        p = Path(env_path)
        if not p.exists():
            raise ConfigError(f"Main config not found: {p}")
        return p

    # 3. Default path
    default = Path.home() / ".config" / "sage" / "config.toml"
    return default if default.exists() else None


def load_main_config(path: Path | None) -> MainConfig | None:
    """Load and parse main config from a TOML file.

    Returns ``None`` if *path* is ``None``.
    """
    if path is None:
        return None

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Failed to read main config {path}: {exc}") from exc

    try:
        data = tomllib.loads(text)
    except Exception as exc:
        raise ConfigError(f"Failed to parse main config {path}: {exc}") from exc

    try:
        return MainConfig(**data)
    except Exception as exc:
        raise ConfigError(f"Invalid main config: {exc}") from exc


def merge_agent_config(
    metadata: dict[str, Any],
    central: MainConfig | None,
    agent_name: str | None = None,
) -> dict[str, Any]:
    """Merge main config defaults and agent overrides into frontmatter metadata.

    Layering (lowest to highest priority):
      1. ``central.defaults``
      2. ``central.agents[agent_name]``  (if present)
      3. *metadata* (frontmatter values)

    Uses top-level replacement semantics — nested objects like ``model_params``
    are replaced wholesale, not deep-merged.
    """
    if central is None:
        return metadata

    # Start with defaults (only explicitly-set fields)
    merged: dict[str, Any] = central.defaults.model_dump(exclude_none=True)

    # Layer agent-specific overrides
    if agent_name and agent_name in central.agents:
        agent_overrides = central.agents[agent_name].model_dump(exclude_none=True)
        merged.update(agent_overrides)

    # Layer frontmatter values (highest priority)
    merged.update(metadata)

    return merged

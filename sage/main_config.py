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
    Permission,
)
from sage.exceptions import ConfigError

logger = logging.getLogger(__name__)


class ConfigOverrides(BaseModel):
    """Fields that can appear in defaults or per-agent overrides."""

    model_config = ConfigDict(extra="forbid")

    model: str | None = None
    model_params: ModelParams | None = None
    max_turns: int | None = None
    permission: Permission | None = None
    context: ContextConfig | None = None
    extensions: list[str] | None = None
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
    """Resolve the main config file path using waterfall lookup.

    Each step falls through to the next if the file is not found:

      1. CLI ``--config`` argument
      2. ``SAGE_CONFIG_PATH`` environment variable
      3. ``./config.toml`` in the current working directory
      4. ``~/.config/sage/config.toml``

    Returns ``None`` when no config file is found at any location.
    """
    # 1. CLI argument
    if cli_path is not None:
        p = Path(cli_path)
        if p.exists():
            return p
        logger.warning("Config not found at CLI path: %s — falling back", p)

    # 2. Environment variable
    env_path = os.environ.get("SAGE_CONFIG_PATH")
    if env_path is not None:
        p = Path(env_path)
        if p.exists():
            return p
        logger.warning("Config not found at SAGE_CONFIG_PATH: %s — falling back", p)

    # 3. Current working directory
    cwd_config = Path.cwd() / "config.toml"
    if cwd_config.exists():
        return cwd_config

    # 4. User home default
    default = Path.home() / ".config" / "sage" / "config.toml"
    return default if default.exists() else None


def load_main_config(path: Path | None) -> MainConfig | None:
    """Load and parse main config from a TOML file.

    Returns ``None`` if *path* is ``None``.  Logs the resolved path and a
    summary of the loaded configuration at INFO level.
    """
    if path is None:
        logger.info("No main config file found")
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
        config = MainConfig(**data)
    except Exception as exc:
        raise ConfigError(f"Invalid main config: {exc}") from exc

    logger.info("Loaded main config from %s", path.resolve())
    return config


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

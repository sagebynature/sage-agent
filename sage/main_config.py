"""Main configuration loading, resolution, and merge for Sage.

Provides a TOML-based main config with a three-tier override system::

    agent .md frontmatter     (highest priority)
    [agents.<name>] in TOML   (agent-specific overrides)
    [defaults] in TOML         (global defaults)

Environment variables are resolved from the ``[env]`` section using
``${VAR}`` syntax, with values sourced from ``os.environ`` (populated
by ``load_dotenv()``).  Resolved values are injected back into
``os.environ`` so downstream libraries (e.g. litellm) pick them up.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from pydantic import BaseModel, ConfigDict, Field

from sage.config import (
    CategoryConfig,
    ContextConfig,
    MCPServerConfig,
    MemoryConfig,
    ModelParams,
    Permission,
    PlanningConfig,
)
from sage.exceptions import ConfigError

logger = logging.getLogger(__name__)


class ConfigOverrides(BaseModel):
    """Fields that can appear in defaults or per-agent overrides."""

    model_config = ConfigDict(extra="forbid")

    model: str | None = None
    model_params: ModelParams | None = None
    max_turns: int | None = None
    max_depth: int | None = None
    permission: Permission | None = None
    shell_dangerous_patterns: list[str] | None = None
    context: ContextConfig | None = None
    extensions: list[str] | None = None
    mcp_servers: dict[str, MCPServerConfig] | None = None
    planning: PlanningConfig | None = None
    memory: MemoryConfig | None = None


class AgentOverrides(ConfigOverrides):
    """Per-agent overrides — adds skills allowlist."""

    skills: list[str] | None = None


class MainConfig(BaseModel):
    """Top-level main configuration loaded from config.toml."""

    model_config = ConfigDict(extra="forbid")

    skills_dir: str | None = None
    agents_dir: str = "agents/"
    primary: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    defaults: ConfigOverrides = Field(default_factory=ConfigOverrides)
    agents: dict[str, AgentOverrides] = Field(default_factory=dict)
    categories: dict[str, CategoryConfig] = Field(default_factory=dict)


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


_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def resolve_and_apply_env(config: MainConfig | None) -> None:
    """Resolve ``${VAR}`` references in ``config.env`` and set ``os.environ``.

    Resolution order:
      1. ``[env]`` values in config.toml (may contain ``${VAR}`` references)
      2. ``os.environ`` (already populated by ``load_dotenv()``)

    Raises :class:`~sage.exceptions.ConfigError` listing all unresolved
    variable references.
    """
    if config is None or not config.env:
        return

    missing: list[str] = []
    resolved: dict[str, str] = {}

    for key, value in config.env.items():
        unresolved_in_value: list[str] = []

        def _replace(match: re.Match[str]) -> str:
            var_name = match.group(1)
            env_val = os.environ.get(var_name)
            if env_val is None:
                unresolved_in_value.append(var_name)
                return match.group(0)  # keep placeholder for error msg
            return env_val

        resolved[key] = _ENV_VAR_RE.sub(_replace, value)
        missing.extend(unresolved_in_value)

    if missing:
        unique = sorted(set(missing))
        raise ConfigError(f"Unresolved env var references in [env]: {', '.join(unique)}")

    for key, value in resolved.items():
        os.environ[key] = value


def _merge_memory(
    defaults: ConfigOverrides,
    agent_overrides: AgentOverrides | None,
    frontmatter: dict[str, Any],
) -> dict[str, Any] | None:
    """Deep-merge memory config from three tiers.

    Returns ``None`` when no tier provides any memory config (preserving
    the existing opt-in behaviour for agents that don't use memory).

    Uses ``model_fields_set`` to apply only fields explicitly written by
    the user at each tier, avoiding accidental propagation of Pydantic
    field defaults from one tier overriding values set at a lower tier.
    """
    has_any = (
        defaults.memory is not None
        or (agent_overrides is not None and agent_overrides.memory is not None)
        or "memory" in frontmatter
    )
    if not has_any:
        return None

    # Start with all MemoryConfig baseline defaults
    merged: dict[str, Any] = MemoryConfig().model_dump()

    # Apply only explicitly-set fields from [defaults.memory]
    if defaults.memory is not None:
        explicitly_set = defaults.memory.model_dump(include=defaults.memory.model_fields_set)
        merged.update(explicitly_set)

    # Apply only explicitly-set fields from [agents.x.memory]
    if agent_overrides is not None and agent_overrides.memory is not None:
        explicitly_set = agent_overrides.memory.model_dump(
            include=agent_overrides.memory.model_fields_set
        )
        merged.update(explicitly_set)

    # Apply all frontmatter memory fields (highest priority, raw dict)
    if "memory" in frontmatter:
        fm_memory = frontmatter["memory"]
        if not isinstance(fm_memory, dict):
            raise ConfigError(
                f"'memory' in agent frontmatter must be a mapping, got {type(fm_memory).__name__}"
            )
        merged.update(fm_memory)

    return merged


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

    Most nested objects use top-level replacement semantics (e.g.
    ``model_params`` is replaced wholesale).  ``memory`` is the exception:
    it is deep-merged field-by-field so individual fields can be overridden
    at each tier without losing fields set at a lower tier.
    """
    if central is None:
        return metadata

    effective_skills: list[str] | None = getattr(central.defaults, "skills", None)
    agent_ovr = central.agents.get(agent_name) if agent_name else None

    # Deep-merge memory separately before the general shallow merge
    memory_merged = _merge_memory(central.defaults, agent_ovr, metadata)

    # Start with defaults (only explicitly-set fields), excluding memory
    merged: dict[str, Any] = central.defaults.model_dump(exclude_none=True)
    merged.pop("memory", None)

    # Layer agent-specific overrides (excluding memory)
    if agent_name and agent_name in central.agents:
        if central.agents[agent_name].skills is not None:
            effective_skills = central.agents[agent_name].skills
        agent_overrides = central.agents[agent_name].model_dump(exclude_none=True)
        agent_overrides.pop("memory", None)
        merged.update(agent_overrides)

    # Layer frontmatter values (excluding memory — handled above)
    merged.update({k: v for k, v in metadata.items() if k != "memory"})

    # Re-attach deep-merged memory (or omit if no tier configured it)
    if memory_merged is not None:
        merged["memory"] = memory_merged

    if effective_skills is not None:
        merged["skills"] = effective_skills

    return merged

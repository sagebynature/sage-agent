"""Configuration loading and validation for Sage."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator

from sage.exceptions import ConfigError

if TYPE_CHECKING:
    from sage.main_config import MainConfig

logger = logging.getLogger(__name__)


class MCPServerConfig(BaseModel):
    """Configuration for an MCP (Model Context Protocol) server connection."""

    transport: Literal["stdio", "sse"] = "stdio"
    command: str | None = None
    url: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class SandboxConfig(BaseModel):
    """Configuration for the shell execution sandbox.

    When ``backend`` is ``"native"`` (the default), commands run with a
    stripped environment (only ``PATH``, ``HOME``, ``USER``, ``LANG``,
    ``TERM`` are passed through).  This blocks ``$SHELL``/env-var bypass
    vectors while remaining portable.

    When ``backend`` is ``"bubblewrap"``, Linux namespace isolation via
    ``bwrap`` is used in addition to environment sanitization.  Requires
    ``bwrap`` to be installed.
    """

    backend: Literal["auto", "native", "bubblewrap", "seatbelt", "docker", "none"] = "native"
    enabled: bool = False
    mode: Literal["read-only", "workspace-write", "full-access"] = "workspace-write"
    workspace: Path = Field(default_factory=Path.cwd)
    writable_roots: list[str] = Field(default_factory=lambda: ["/tmp"])
    deny_read: list[str] = Field(default_factory=lambda: ["~/.ssh", "~/.aws", "~/.gnupg"])
    allowed_env: list[str] = Field(default_factory=list)
    network: bool = True
    timeout: float = 30.0


class CredentialScrubConfig(BaseModel):
    """Configuration for the credential scrubbing hook."""

    enabled: bool = False
    patterns: list[str] = Field(default_factory=list)
    allowlist: list[str] = Field(default_factory=list)


class ClassificationRuleConfig(BaseModel):
    """A single classification rule mapping a pattern to a model."""

    pattern: str
    model: str
    priority: int = 0


class QueryClassificationConfig(BaseModel):
    """Configuration for the query classification hook."""

    rules: list[ClassificationRuleConfig] = Field(default_factory=list)


class ResearchConfig(BaseModel):
    """Configuration for the pre-response research phase."""

    enabled: bool = False
    max_sources: int = 3
    timeout: float = 10.0


class FollowThroughConfig(BaseModel):
    """Configuration for the follow-through guardrail hook."""

    enabled: bool = False
    patterns: list[str] = Field(
        default_factory=lambda: ["I cannot", "I'm unable", "I don't have access"]
    )


class SessionConfig(BaseModel):
    """Configuration for session lifecycle management."""

    enabled: bool = False


class MemoryConfig(BaseModel):
    """Configuration for the agent memory backend."""

    backend: Literal["sqlite", "file"] = "sqlite"
    path: str = "memory.db"
    auto_load: bool = False
    auto_load_top_k: int = 5
    embedding: str = "text-embedding-3-large"
    compaction_threshold: int = 50
    vector_search: Literal["auto", "sqlite_vec", "numpy"] = "auto"
    min_exchange_length: int = 100
    relevance_filter: Literal["none", "length", "llm"] = "none"
    relevance_threshold: float = 0.5


class ModelParams(BaseModel):
    """Optional model-level parameters passed to the LLM provider.

    Only the fields that are explicitly set are forwarded to the provider;
    unset fields are omitted so provider defaults apply.
    """

    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    top_k: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    seed: int | None = None
    stop: list[str] | None = None
    timeout: float | None = None
    response_format: dict[str, Any] | None = None
    num_retries: int | None = None
    retry_after: float | None = None

    def to_kwargs(self) -> dict[str, Any]:
        """Return only the explicitly set parameters (exclude None values)."""
        return self.model_dump(exclude_none=True)


# Type aliases for permission configuration
PermissionAction = Literal["allow", "deny", "ask"]
PermissionValue = Union[PermissionAction, Dict[str, PermissionAction]]


class Permission(BaseModel):
    """Granular permission configuration for specific tools/categories."""

    model_config = ConfigDict(extra="allow")

    read: PermissionValue | None = None
    edit: PermissionValue | None = None
    shell: PermissionValue | None = None
    web: PermissionValue | None = None
    memory: PermissionValue | None = None
    task: PermissionValue | None = None
    git: PermissionValue | None = None


class ContextConfig(BaseModel):
    """Token-aware context management configuration."""

    compaction_threshold: float = 0.75
    reserve_tokens: int = 4096
    prune_tool_outputs: bool = True
    tool_output_max_chars: int = 5000


class GitConfig(BaseModel):
    """Git integration configuration."""

    auto_snapshot: bool = True
    auto_commit_dirty: bool = False
    auto_commit_edits: bool = False


class TracingConfig(BaseModel):
    """OpenTelemetry tracing configuration.

    Requires ``pip install sage-agent[tracing]`` (opentelemetry-api + sdk).
    The ``"otlp"`` exporter additionally requires
    ``opentelemetry-exporter-otlp-proto-grpc``.
    """

    enabled: bool = False
    service_name: str = "sage-agent"
    exporter: Literal["none", "console", "otlp"] = "none"


class IdentityConfig(BaseModel):
    """Configuration for optional AIEOS identity / persona."""

    format: Literal["aieos", "none"] = "none"
    file: str | None = None


class AgentConfig(BaseModel):
    """Top-level configuration for a Sage agent.

    Subagents can be referenced as plain directory/file strings, via the
    ``config`` field, or defined inline::

        subagents:
          - research_agent            # directory containing AGENTS.md
          - config: researcher.md     # path relative to this file
          - config: ../shared/critic.md
          - name: inline-helper       # inline definition
            model: gpt-4o-mini

    Plain strings are treated as ``config`` references (paths or directories).
    When ``config`` is set, all other fields are ignored — the referenced
    file is loaded in full.  At the top level (loaded directly via
    :func:`load_config`), ``name`` and ``model`` are always required.

    Key prompt fields:
    - ``description``: display/discovery metadata only; never sent to the LLM
    - ``_body``: markdown body content captured from the file and used as the
      runtime system prompt
    """

    model_config = ConfigDict(extra="forbid")

    config: str | None = None  # path to external .md file (subagent refs only)
    name: str = ""
    model: str = ""
    description: str = ""  # display/discovery ONLY - NOT sent to model
    _body: str = PrivateAttr(default="")  # markdown body = system prompt
    permission: Permission | None = None
    extensions: list[str] = Field(default_factory=list)
    memory: MemoryConfig | None = None
    subagents: list[AgentConfig] = Field(default_factory=list)
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)
    max_turns: int = 10
    max_depth: int = 3
    model_params: ModelParams = Field(default_factory=ModelParams)
    skills: list[str] | None = None
    context: ContextConfig | None = None
    git: GitConfig | None = None
    sandbox: SandboxConfig | None = None
    tracing: TracingConfig | None = None
    parallel_tool_execution: bool = True
    tool_timeout: float | None = None
    credential_scrubbing: CredentialScrubConfig | None = None
    query_classification: QueryClassificationConfig | None = None
    research: ResearchConfig | None = None
    follow_through: FollowThroughConfig | None = None
    session: SessionConfig | None = None
    identity: IdentityConfig | None = None

    @field_validator("subagents", mode="before")
    @classmethod
    def _coerce_string_subagents(cls, v: Any) -> Any:
        """Allow plain strings in the subagents list as shorthand for config refs.

        ``- research_agent`` becomes ``- config: research_agent``.
        """
        if not isinstance(v, list):
            return v
        coerced: list[Any] = []
        for item in v:
            if isinstance(item, str):
                coerced.append({"config": item})
            else:
                coerced.append(item)
        return coerced

    @model_validator(mode="after")
    def validate_name_and_model(self) -> AgentConfig:
        """Require name unless this is a config-file reference.

        ``model`` is no longer validated here — it is checked post-merge in
        :func:`load_config` so that main config defaults can supply it.
        """

        if self.config is None:
            if not self.name:
                raise ValueError(
                    "'name' is required (or use 'config: path.md' to reference an external file)"
                )
        return self


def load_config(path: str | Path, central: MainConfig | None = None) -> AgentConfig:
    """Load and validate an agent configuration from a Markdown file.

    The markdown file must contain YAML frontmatter with agent config fields
    and may include a markdown body that becomes ``AgentConfig._body``.

    When *central* is provided, the frontmatter is merged with main config
    defaults and per-agent overrides before constructing the ``AgentConfig``.

    Args:
        path: Path to the markdown configuration file with YAML frontmatter.
        central: Optional main config for default/override resolution.

    Returns:
        A validated :class:`AgentConfig` instance.

    Raises:
        ConfigError: If the file cannot be read, parsed, or validated.
    """
    config_path = Path(path)

    # If a directory is given, look for AGENTS.md inside it.
    if config_path.is_dir():
        config_path = config_path / "AGENTS.md"

    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Failed to read config file {config_path}: {exc}") from exc

    # Parse frontmatter
    from sage.frontmatter import parse_frontmatter

    metadata, body = parse_frontmatter(raw)

    if not isinstance(metadata, dict):
        raise ConfigError(
            f"Config file must contain valid YAML frontmatter, got {type(metadata).__name__}"
        )

    # Merge with main config (defaults → agent overrides → frontmatter)
    from sage.main_config import merge_agent_config

    agent_name = metadata.get("name")
    merged = merge_agent_config(metadata, central, agent_name)

    try:
        config = AgentConfig(**merged)
    except Exception as exc:
        raise ConfigError(f"Invalid agent configuration: {exc}") from exc

    # Post-merge validation: model must be present after all layers are applied
    if not config.model:
        raise ConfigError(
            f"'model' is required for agent '{config.name}' "
            "(set it in the agent .md file, main config [agents.<name>], "
            "or main config [defaults])"
        )

    # Store the markdown body as _body (system prompt)
    config._body = body

    base_dir = config_path.parent
    config = _resolve_subagent_refs(config, base_dir, central)

    # Auto-discover subagents for the primary agent when not explicitly specified.
    if (
        not config.subagents
        and "subagents" not in metadata
        and central is not None
        and central.primary
        and config.name == central.primary
    ):
        config = _auto_discover_subagents(config, base_dir, central)

    # Log the effective (post-merge) agent configuration.
    logger.info("Agent '%s' loaded from %s", config.name, config_path)
    logger.info(
        "  model=%s, max_turns=%d, permission=%s, extensions=%s",
        config.model,
        config.max_turns,
        config.permission,
        config.extensions,
    )
    if config.model_params and config.model_params.to_kwargs():
        logger.info("  model_params=%s", config.model_params.to_kwargs())
    if config.context:
        logger.info(
            "  context: compaction_threshold=%.2f, reserve_tokens=%d",
            config.context.compaction_threshold,
            config.context.reserve_tokens,
        )
    if config.memory:
        logger.info(
            "  memory: backend=%s, path=%s, embedding=%s, compaction_threshold=%d, vector_search=%s",
            config.memory.backend,
            config.memory.path,
            config.memory.embedding,
            config.memory.compaction_threshold,
            config.memory.vector_search,
        )
    if config.mcp_servers:
        logger.info("  mcp_servers: %d configured", len(config.mcp_servers))
    if config.subagents:
        logger.info("  subagents: %s", [s.name for s in config.subagents])
    return config


def _resolve_subagent_refs(
    config: AgentConfig, base_dir: Path, central: MainConfig | None = None
) -> AgentConfig:
    """Replace any subagent ``config: path.md`` references with loaded configs.

    Subagents that use the ``config`` field are loaded from their referenced
    file (relative to ``base_dir``) and merged with *central* config.
    Inline subagents are **not** merged with main config (they must be
    fully specified) but are recursed into so their own nested refs are resolved.
    """
    resolved: list[AgentConfig] = []
    for sub in config.subagents:
        if sub.config is not None:
            ref_path = base_dir / sub.config
            resolved.append(load_config(ref_path, central=central))
        else:
            # Inline subagents must be fully specified
            if not sub.model:
                raise ConfigError(
                    f"Inline subagent '{sub.name}' must specify 'model' "
                    "(inline subagents are not merged with main config)"
                )
            resolved.append(_resolve_subagent_refs(sub, base_dir, central))
    return config.model_copy(update={"subagents": resolved})


def _auto_discover_subagents(
    config: AgentConfig, base_dir: Path, central: MainConfig | None = None
) -> AgentConfig:
    """Auto-discover subagents from sibling ``.md`` files in *base_dir*.

    Used when the primary agent omits the ``subagents`` field, making all
    other agents in ``agents_dir`` available for delegation.
    """
    discovered: list[AgentConfig] = []
    for md_file in sorted(base_dir.glob("*.md")):
        if md_file.stem == config.name:
            continue
        try:
            sub_config = load_config(md_file, central=central)
            discovered.append(sub_config)
        except ConfigError as exc:
            logger.warning("Skipping %s during auto-discovery: %s", md_file, exc)

    if discovered:
        logger.info(
            "Auto-discovered %d subagent(s) for '%s': %s",
            len(discovered),
            config.name,
            [s.name for s in discovered],
        )
    return config.model_copy(update={"subagents": discovered})

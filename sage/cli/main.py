"""Sage CLI."""

from __future__ import annotations

import asyncio
import logging
import logging.config
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from dotenv import load_dotenv

from sage.config import load_config
from sage.exceptions import SageError, ConfigError

if TYPE_CHECKING:
    from sage.main_config import MainConfig

# Default search locations for logging.conf (checked in order):
#   1. Explicit --log-config CLI option
#   2. Current working directory
#   3. Project root (one level above the sage package)
_PACKAGE_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_LOG_CONFIG_CANDIDATES = [
    Path.cwd() / "logging.conf",
    _PACKAGE_DIR.parent / "logging.conf",
]


def _setup_logging(config_path: str | None = None, verbose: bool = False) -> None:
    """Initialize logging from a config file with optional verbose override."""
    log_config: Path | None = None
    if config_path is not None:
        log_config = Path(config_path)
    else:
        for candidate in _DEFAULT_LOG_CONFIG_CANDIDATES:
            if candidate.is_file():
                log_config = candidate
                break

    if log_config is not None and log_config.is_file():
        logging.config.fileConfig(str(log_config), disable_existing_loggers=False)
    else:
        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.WARNING,
            format="%(asctime)s|%(name)s:%(funcName)s:L%(lineno)s|%(levelname)s %(message)s",
        )

    if verbose:
        logging.getLogger("sage").setLevel(logging.DEBUG)


def _get_main_config(ctx: click.Context) -> MainConfig | None:
    """Extract main config from click context."""
    obj = ctx.ensure_object(dict)
    return obj.get("main_config")


@click.group()
@click.version_option(version="0.1.0", prog_name="sage")
@click.option(
    "--config",
    "main_config_path",
    default=None,
    help="Path to main config.toml (also reads SAGE_CONFIG_PATH env var)",
)
@click.option(
    "--log-config",
    "log_config_path",
    default=None,
    help="Path to logging.conf (default: auto-detected from cwd or project root)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable debug logging for sage internals",
)
@click.pass_context
def cli(
    ctx: click.Context, main_config_path: str | None, log_config_path: str | None, verbose: bool
) -> None:
    """Sage - AI agent definition and deployment."""
    load_dotenv()
    _setup_logging(log_config_path, verbose)
    ctx.ensure_object(dict)
    from sage.main_config import resolve_main_config_path, load_main_config

    resolved = resolve_main_config_path(main_config_path)
    ctx.obj["main_config"] = load_main_config(resolved)


@cli.group()
def agent() -> None:
    """Agent commands."""


@agent.command("run")
@click.argument("config_path", type=click.Path(exists=True))
@click.option("--input", "-i", "user_input", required=True, help="Input to send to the agent")
@click.option("--stream", "use_stream", is_flag=True, help="Stream the response")
@click.pass_context
def agent_run(ctx: click.Context, config_path: str, user_input: str, use_stream: bool) -> None:
    """Run an agent from a config file."""
    try:
        main_config = _get_main_config(ctx)
        asyncio.run(_agent_run(config_path, user_input, use_stream, main_config))
    except SageError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def _agent_run(
    config_path: str,
    user_input: str,
    use_stream: bool,
    main_config: MainConfig | None = None,
) -> None:
    from sage.agent import Agent

    agent = Agent.from_config(config_path, central=main_config)
    try:
        if use_stream:
            async for chunk in agent.stream(user_input):
                click.echo(chunk, nl=False)
            click.echo()  # Final newline
        else:
            result = await agent.run(user_input)
            click.echo(result)
    finally:
        await agent.close()


@agent.command("orchestrate")
@click.argument("config_path", type=click.Path(exists=True))
@click.option("--input", "-i", "user_input", required=True, help="Input to send to all subagents")
@click.pass_context
def agent_orchestrate(ctx: click.Context, config_path: str, user_input: str) -> None:
    """Run all subagents of an orchestrator config in parallel."""
    try:
        main_config = _get_main_config(ctx)
        asyncio.run(_agent_orchestrate(config_path, user_input, main_config))
    except SageError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def _agent_orchestrate(
    config_path: str, user_input: str, main_config: MainConfig | None = None
) -> None:
    from sage.agent import Agent
    from sage.orchestrator.parallel import Orchestrator

    parent = Agent.from_config(config_path, central=main_config)
    if not parent.subagents:
        click.echo("No subagents defined in config.", err=True)
        sys.exit(1)

    agents = list(parent.subagents.values())
    click.echo(
        f"Running {len(agents)} subagents in parallel: {', '.join(a.name for a in agents)}\n"
    )

    results = await Orchestrator.run_parallel(agents, user_input)

    for result in results:
        click.echo(f"── {result.agent_name} {'✓' if result.success else '✗'} ──")
        if result.success:
            click.echo(result.output)
        else:
            click.echo(f"Error: {result.error}", err=True)
        click.echo()


@agent.command("validate")
@click.argument("config_path", type=click.Path(exists=True))
@click.pass_context
def agent_validate(ctx: click.Context, config_path: str) -> None:
    """Validate an agent config file without running."""
    try:
        main_config = _get_main_config(ctx)
        config = load_config(config_path, central=main_config)
        click.echo(f"Config valid: {config.name} (model: {config.model})")
        if config.extensions:
            click.echo(f"  Extensions: {', '.join(config.extensions)}")
        if config.permission:
            click.echo(f"  Permission: {config.permission.model_dump(exclude_none=True)}")
        if config.subagents:
            click.echo(f"  Subagents: {', '.join(s.name for s in config.subagents)}")
        if config.mcp_servers:
            click.echo(f"  MCP servers: {len(config.mcp_servers)}")
    except ConfigError as e:
        click.echo(f"Invalid config: {e}", err=True)
        sys.exit(1)


@agent.command("list")
@click.argument("directory", type=click.Path(exists=True), default=".")
@click.pass_context
def agent_list(ctx: click.Context, directory: str) -> None:
    """List agent config files in a directory."""
    main_config = _get_main_config(ctx)
    dir_path = Path(directory)
    configs = sorted(dir_path.glob("**/*.md"))

    if not configs:
        click.echo("No agent config files found.")
        return

    for path in configs:
        try:
            config = load_config(str(path), central=main_config)
            click.echo(f"  {path}: {config.name} ({config.model})")
        except ConfigError:
            click.echo(f"  {path}: [invalid config]")


@cli.group()
def tool() -> None:
    """Tool commands."""


@tool.command("list")
@click.argument("config_path", type=click.Path(exists=True))
@click.pass_context
def tool_list(ctx: click.Context, config_path: str) -> None:
    """List available tools for an agent config."""
    try:
        main_config = _get_main_config(ctx)
        config = load_config(config_path, central=main_config)
        if not config.extensions and not config.permission:
            click.echo("No tools configured.")
            return

        click.echo(f"Tools for {config.name}:")
        if config.extensions:
            click.echo("  Extensions:")
            for ext in config.extensions:
                click.echo(f"    - {ext}")
        if config.permission:
            # Show non-deny permission categories
            perm_dict = config.permission.model_dump(exclude_none=True)
            if perm_dict:
                click.echo("  Permissions:")
                for key, value in perm_dict.items():
                    if value != "deny":
                        click.echo(f"    {key}: {value}")
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--name", "-n", default="my-agent", help="Agent name")
@click.option("--model", "-m", default="gpt-4o", help="Model to use")
def init(name: str, model: str) -> None:
    """Scaffold a new `AGENTS.md` project."""
    md_content = f"""---
name: {name}
model: {model}
max_turns: 10

memory:
  backend: sqlite
  path: memory.db
---

You are {name}, a helpful AI assistant.

Be concise and accurate in your responses.
"""

    md_path = Path("AGENTS.md")

    if md_path.exists():
        click.echo("AGENTS.md already exists. Aborting.", err=True)
        sys.exit(1)

    md_path.write_text(md_content)

    click.echo(f"Created {md_path}")
    click.echo("\nRun with: sage agent run AGENTS.md -i 'Hello!'")


@cli.command()
@click.option(
    "--agent-config",
    "-c",
    "config_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to AGENTS.md or directory containing AGENTS.md",
)
@click.pass_context
def tui(ctx: click.Context, config_path: str) -> None:
    """Launch the interactive TUI for an agent config."""
    from sage.cli.tui import SageTUIApp

    main_config = _get_main_config(ctx)
    path = Path(config_path)
    if path.is_dir():
        path = path / "AGENTS.md"
    app = SageTUIApp(config_path=path, central=main_config)
    app.run()

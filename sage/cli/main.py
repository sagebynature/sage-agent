"""Sage CLI."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import apollo_logging  # type: ignore
import click
from dotenv import load_dotenv

from sage.config import load_config
from sage.exceptions import SageError, ConfigError

if TYPE_CHECKING:
    from sage.central_config import CentralConfig


def _get_central(ctx: click.Context) -> CentralConfig | None:
    """Extract central config from click context."""
    obj = ctx.ensure_object(dict)
    return obj.get("central_config")


@click.group()
@click.version_option(version="0.1.0", prog_name="sage")
@click.option(
    "--config",
    "central_config_path",
    default=None,
    help="Path to central config.toml (also reads SAGE_CONFIG_PATH env var)",
)
@click.pass_context
def cli(ctx: click.Context, central_config_path: str | None) -> None:
    """Sage - AI agent definition and deployment."""
    load_dotenv()
    if Path("logging.conf").exists():
        apollo_logging.init("logging.conf")
    ctx.ensure_object(dict)
    from sage.central_config import resolve_central_config_path, load_central_config

    resolved = resolve_central_config_path(central_config_path)
    ctx.obj["central_config"] = load_central_config(resolved)


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
        central = _get_central(ctx)
        asyncio.run(_agent_run(config_path, user_input, use_stream, central))
    except SageError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def _agent_run(
    config_path: str,
    user_input: str,
    use_stream: bool,
    central: CentralConfig | None = None,
) -> None:
    from sage.agent import Agent

    agent = Agent.from_config(config_path, central=central)

    if use_stream:
        async for chunk in agent.stream(user_input):
            click.echo(chunk, nl=False)
        click.echo()  # Final newline
    else:
        result = await agent.run(user_input)
        click.echo(result)


@agent.command("orchestrate")
@click.argument("config_path", type=click.Path(exists=True))
@click.option("--input", "-i", "user_input", required=True, help="Input to send to all subagents")
@click.pass_context
def agent_orchestrate(ctx: click.Context, config_path: str, user_input: str) -> None:
    """Run all subagents of an orchestrator config in parallel."""
    try:
        central = _get_central(ctx)
        asyncio.run(_agent_orchestrate(config_path, user_input, central))
    except SageError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def _agent_orchestrate(
    config_path: str, user_input: str, central: CentralConfig | None = None
) -> None:
    from sage.agent import Agent
    from sage.orchestrator.parallel import Orchestrator

    parent = Agent.from_config(config_path, central=central)
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
        central = _get_central(ctx)
        config = load_config(config_path, central=central)
        click.echo(f"Config valid: {config.name} (model: {config.model})")
        if config.tools:
            click.echo(f"  Tools: {', '.join(config.tools)}")
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
    central = _get_central(ctx)
    dir_path = Path(directory)
    configs = sorted(dir_path.glob("**/*.md"))

    if not configs:
        click.echo("No agent config files found.")
        return

    for path in configs:
        try:
            config = load_config(str(path), central=central)
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
        central = _get_central(ctx)
        config = load_config(config_path, central=central)
        if not config.tools:
            click.echo("No tools configured.")
            return

        click.echo(f"Tools for {config.name}:")
        for tool_path in config.tools:
            click.echo(f"  - {tool_path}")
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
tools: []
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

    central = _get_central(ctx)
    path = Path(config_path)
    if path.is_dir():
        path = path / "AGENTS.md"
    app = SageTUIApp(config_path=path, central=central)
    app.run()

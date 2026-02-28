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
from sage.cli.exit_codes import SageExitCode

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
    from sage.main_config import resolve_main_config_path, load_main_config, resolve_and_apply_env

    resolved = resolve_main_config_path(main_config_path)
    ctx.obj["main_config"] = load_main_config(resolved)
    resolve_and_apply_env(ctx.obj["main_config"])


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
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
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


# ---------------------------------------------------------------------------
# Lazy exception imports for exec_cmd error handlers
# ---------------------------------------------------------------------------
try:
    from sage.exceptions import PermissionError as _PermissionError  # type: ignore[assignment]
    from sage.exceptions import MaxTurnsExceeded as _MaxTurnsExceeded
    from sage.exceptions import ToolError as _ToolError
    from sage.exceptions import ProviderError as _ProviderError
except ImportError:  # pragma: no cover
    _PermissionError = Exception  # type: ignore[assignment,misc]
    _MaxTurnsExceeded = Exception  # type: ignore[assignment,misc]
    _ToolError = Exception  # type: ignore[assignment,misc]
    _ProviderError = Exception  # type: ignore[assignment,misc]


@cli.command("exec")
@click.argument("config_path", type=click.Path(exists=True))
@click.option("--input", "-i", "user_input", default=None, help="Input to send to the agent")
@click.option(
    "--output",
    "-o",
    "output_mode",
    type=click.Choice(["text", "jsonl", "quiet"]),
    default="text",
    show_default=True,
    help="Output format: text (human-readable), jsonl (machine-readable), quiet (no output)",
)
@click.option(
    "--timeout",
    type=float,
    default=None,
    help="Maximum wall-clock seconds for the agent run (0 = no limit)",
)
@click.option("--stdin", "use_stdin", is_flag=True, help="Read user input from stdin")
@click.option("--yes", "ask_yes", is_flag=True, help="Auto-approve all ASK-gated tool calls")
@click.option(
    "--deny-all",
    "deny_all",
    is_flag=True,
    default=False,
    help="Auto-deny all ASK-gated tool calls (default CI behaviour)",
)
@click.pass_context
def exec_cmd(
    ctx: click.Context,
    config_path: str,
    user_input: str | None,
    output_mode: str,
    timeout: float | None,
    use_stdin: bool,
    ask_yes: bool,
    deny_all: bool,
) -> None:
    """Run an agent in CI/headless mode with structured exit codes.

    By default all ASK-gated tool calls are denied (\\--deny-all is the
    implicit default for ``sage exec``). Pass \\--yes to auto-approve.

    Exit codes:\\n
      0  success\\n
      1  generic / unclassified error\\n
      2  config error\\n
      3  permission denied\\n
      4  max turns exceeded\\n
      5  timeout\\n
      6  tool error\\n
      7  provider error\\n
    """
    # Resolve input source.
    if use_stdin:
        user_input = sys.stdin.read().rstrip("\n")
    if not user_input:
        click.echo("Error: no input provided. Use -i / --input or --stdin.", err=True)
        sys.exit(SageExitCode.ERROR)

    # --yes beats implicit deny-all.
    if ask_yes:
        ask_policy = "allow"
    else:
        # Default for sage exec: deny all ASK-gated calls.
        ask_policy = "deny"

    from sage.cli.output import make_writer

    writer = make_writer(output_mode)
    main_config = _get_main_config(ctx)

    try:
        coro = _exec_run(config_path, user_input, ask_policy, writer, main_config)
        if timeout is not None and timeout > 0:

            async def _with_timeout() -> None:
                await asyncio.wait_for(coro, timeout=timeout)

            asyncio.run(_with_timeout())
        else:
            asyncio.run(coro)
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(SageExitCode.CONFIG_ERROR)
    except _PermissionError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(SageExitCode.PERMISSION_DENIED)
    except _MaxTurnsExceeded as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(SageExitCode.MAX_TURNS)
    except asyncio.TimeoutError:
        click.echo("Error: agent run timed out.", err=True)
        sys.exit(SageExitCode.TIMEOUT)
    except _ToolError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(SageExitCode.TOOL_ERROR)
    except _ProviderError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(SageExitCode.PROVIDER_ERROR)
    except SageError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(SageExitCode.ERROR)
    finally:
        writer.close()


async def _exec_run(
    config_path: str,
    user_input: str,
    ask_policy: str,
    writer: object,
    main_config: MainConfig | None = None,
) -> None:
    """Inner async coroutine for ``sage exec``."""
    from sage.agent import Agent
    from sage.cli.output import OutputWriter

    agent = Agent.from_config(config_path, central=main_config)
    # Wire the ask policy into the tool registry.
    if hasattr(agent, "tool_registry") and hasattr(agent.tool_registry, "set_ask_policy"):
        agent.tool_registry.set_ask_policy(ask_policy)  # type: ignore[arg-type]
    try:
        result = await agent.run(user_input)
        assert isinstance(writer, OutputWriter)
        writer.write_result(result)
    finally:
        await agent.close()


# ---------------------------------------------------------------------------
# eval command group
# ---------------------------------------------------------------------------


@cli.group("eval")
def eval_group() -> None:
    """Evaluation commands."""


@eval_group.command("run")
@click.argument("suite_yaml", type=click.Path(exists=True))
@click.option("--model", "-m", "model", default=None, help="Override model")
@click.option("--runs", "runs_per_case", default=1, show_default=True, help="Runs per test case")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format",
)
@click.option(
    "--min-pass-rate",
    "min_pass_rate",
    default=None,
    type=float,
    help="Fail (exit 1) if pass rate is below this threshold (0.0–1.0)",
)
@click.pass_context
def eval_run(
    ctx: click.Context,
    suite_yaml: str,
    model: str | None,
    runs_per_case: int,
    output_format: str,
    min_pass_rate: float | None,
) -> None:
    """Run an eval suite and report results."""
    try:
        asyncio.run(_eval_run(suite_yaml, model, runs_per_case, output_format, min_pass_rate))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _run_single_model(suite_yaml: str, model: str, runs_per_case: int) -> str:
    """Run eval for a single model in a separate process.

    Returns the EvalRunResult serialised as JSON to avoid pickle
    compatibility issues across process boundaries.
    """
    from sage.eval.runner import EvalRunner
    from sage.eval.suite import load_suite

    suite = load_suite(suite_yaml)
    runner = EvalRunner(suite, model=model)
    result = asyncio.run(runner.run(runs_per_case=runs_per_case))
    return result.model_dump_json()


async def _eval_run(
    suite_yaml: str,
    model: str | None,
    runs_per_case: int,
    output_format: str,
    min_pass_rate: float | None,
) -> None:
    from concurrent.futures import ProcessPoolExecutor

    from sage.eval.history import EvalHistory
    from sage.eval.report import format_run_json, format_run_text
    from sage.eval.runner import EvalRunner, EvalRunResult
    from sage.eval.suite import load_suite

    suite = load_suite(suite_yaml)

    # When a specific model is given via --model, run only that model.
    # Otherwise, run every model listed in the suite settings.
    models = [model] if model else suite.settings.models

    # Run each model.  When there are multiple models, use separate
    # processes so that os.chdir() calls in the runner don't race.
    if len(models) == 1:
        runner = EvalRunner(suite, model=models[0])
        results: list[EvalRunResult | Exception] = [await runner.run(runs_per_case=runs_per_case)]
    else:
        loop = asyncio.get_running_loop()
        with ProcessPoolExecutor(max_workers=len(models)) as pool:
            futures = [
                loop.run_in_executor(pool, _run_single_model, suite_yaml, m, runs_per_case)
                for m in models
            ]
            raw = await asyncio.gather(*futures, return_exceptions=True)

        results = []
        for m, r in zip(models, raw):
            if isinstance(r, Exception):
                click.echo(f"Error running model {m}: {r}", err=True)
                results.append(r)
            else:
                results.append(EvalRunResult.model_validate_json(r))

    history = EvalHistory()
    await history.init_db()

    failed = False
    for m, result in zip(models, results):
        if isinstance(result, Exception):
            failed = True
            continue

        if output_format == "json":
            click.echo(format_run_json(result))
        else:
            click.echo(format_run_text(result))

        await history.save_run(result)

        if min_pass_rate is not None and result.pass_rate < min_pass_rate:
            click.echo(
                f"Pass rate {result.pass_rate:.1%} below threshold {min_pass_rate:.1%} for model {m}",
                err=True,
            )
            failed = True

    if failed:
        sys.exit(1)


@eval_group.command("validate")
@click.argument("suite_yaml", type=click.Path(exists=True))
def eval_validate(suite_yaml: str) -> None:
    """Validate a suite YAML file without running."""
    try:
        from sage.eval.suite import load_suite

        suite = load_suite(suite_yaml)
        click.echo(
            f"Suite valid: {suite.name} — {len(suite.test_cases)} test case(s), agent: {suite.agent}"
        )
    except Exception as e:
        click.echo(f"Invalid suite: {e}", err=True)
        sys.exit(1)


@eval_group.command("history")
@click.option("--suite", "suite_name", default=None, help="Filter by suite name")
@click.option("--last", "last", default=20, show_default=True, help="Number of runs to show")
def eval_history(suite_name: str | None, last: int) -> None:
    """Show eval run history."""
    try:
        asyncio.run(_eval_history(suite_name, last))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def _eval_history(suite_name: str | None, last: int) -> None:
    from sage.eval.history import EvalHistory

    history = EvalHistory()
    await history.init_db()
    runs = await history.list_runs(suite_name=suite_name, last=last)
    if not runs:
        click.echo("No eval runs found.")
        return
    click.echo(f"{'ID':>36}  {'Suite':<20}  {'Model':<15}  {'Pass':>6}  {'Score':>6}")
    click.echo("-" * 90)
    for r in runs:
        click.echo(
            f"{r['id']:>36}  {r['suite_name']:<20}  {r['model']:<15}  "
            f"{r['pass_rate']:.1%}  {r['avg_score']:.3f}"
        )


@eval_group.command("compare")
@click.argument("run_id_1")
@click.argument("run_id_2")
def eval_compare(run_id_1: str, run_id_2: str) -> None:
    """Compare two eval runs side by side."""
    try:
        asyncio.run(_eval_compare(run_id_1, run_id_2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def _eval_compare(run_id_1: str, run_id_2: str) -> None:
    from sage.eval.history import EvalHistory
    from sage.eval.report import format_comparison_text

    history = EvalHistory()
    await history.init_db()
    comparison = await history.compare_runs(run_id_1, run_id_2)
    click.echo(format_comparison_text(comparison))


@eval_group.command("list")
@click.argument("directory", type=click.Path(exists=True), default=".")
def eval_list(directory: str) -> None:
    """List eval suite YAML files in a directory."""
    from sage.eval.suite import load_suite

    dir_path = Path(directory)
    yamls = sorted(list(dir_path.glob("**/*.yaml")) + list(dir_path.glob("**/*.yml")))
    if not yamls:
        click.echo("No YAML files found.")
        return
    for yaml_path in yamls:
        try:
            suite = load_suite(str(yaml_path))
            click.echo(
                f"  {yaml_path}: {suite.name} ({len(suite.test_cases)} cases, agent: {suite.agent})"
            )
        except Exception:
            pass  # skip non-suite YAML files

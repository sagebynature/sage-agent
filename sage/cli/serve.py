"""JSON-RPC server CLI command."""

from __future__ import annotations

import asyncio
import logging
import logging.config
import sys

import click

from sage.agent import Agent
from sage.coordination.session import PersistentSessionManager
from sage.protocol.bridge import EventBridge
from sage.protocol.dispatcher import MethodDispatcher
from sage.protocol.server import JsonRpcServer

logger = logging.getLogger(__name__)


async def _serve(
    agent_config: str | None = None, verbose: bool = False, yolo: bool = False
) -> None:
    server = JsonRpcServer(agent_config=agent_config, verbose=verbose)

    agent = Agent.from_config(agent_config) if agent_config is not None else None
    session_manager = PersistentSessionManager()
    dispatcher = MethodDispatcher(agent=agent, session_manager=session_manager, server=server)
    server.set_dispatcher(dispatcher)

    if agent is not None:
        bridge = EventBridge(server=server, agent=agent)
        bridge.setup()

        if yolo:
            from sage.permissions import AllowAllPermissionHandler, enable_permission_bypass

            permission_handler = AllowAllPermissionHandler()
            for subagent in getattr(agent, "subagents", {}).values():
                enable_permission_bypass(subagent)
        else:
            from sage.protocol.permissions import JsonRpcPermissionHandler

            permission_handler = JsonRpcPermissionHandler(server=server, dispatcher=dispatcher)
        if hasattr(agent, "tool_registry") and agent.tool_registry is not None:
            agent.tool_registry.set_permission_handler(permission_handler)

    await server.start()


@click.command("serve")
@click.option(
    "--agent-config",
    type=click.Path(exists=True),
    default=None,
    help="Path to agent configuration file",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose logging",
)
@click.option("--yolo", "-y", is_flag=True, default=False, help="Bypass all tool permission checks")
@click.pass_context
def serve(ctx: click.Context, agent_config: str | None, verbose: bool, yolo: bool) -> None:
    """Start JSON-RPC server for TUI communication.

    Reads newline-delimited JSON-RPC 2.0 requests from stdin.
    Writes newline-delimited JSON-RPC 2.0 responses to stdout.
    All logging goes to stderr.

    Example:
        echo '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{}}' | sage serve
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s|%(name)s:%(funcName)s:L%(lineno)s|%(levelname)s %(message)s",
        stream=sys.stderr,
    )

    if verbose:
        logging.getLogger("sage").setLevel(logging.DEBUG)

    if agent_config is None:
        from sage.cli.main import _resolve_primary_agent
        from sage.exceptions import ConfigError

        obj = ctx.ensure_object(dict)
        main_config = obj.get("main_config")
        main_config_path = obj.get("main_config_path")
        try:
            agent_config = _resolve_primary_agent(main_config, main_config_path)
        except ConfigError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    effective_yolo = yolo or bool(ctx.ensure_object(dict).get("yolo"))
    asyncio.run(_serve(agent_config, verbose, effective_yolo))

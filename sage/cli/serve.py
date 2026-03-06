"""JSON-RPC server CLI command."""

from __future__ import annotations

import asyncio
import logging
import logging.config
import sys

import click

from sage.agent import Agent
from sage.coordination.session import PersistentSessionManager
from sage.protocol.dispatcher import MethodDispatcher
from sage.protocol.server import JsonRpcServer

logger = logging.getLogger(__name__)


async def _serve(agent_config: str | None = None, verbose: bool = False) -> None:
    server = JsonRpcServer(agent_config=agent_config, verbose=verbose)

    agent = Agent.from_config(agent_config) if agent_config is not None else None
    session_manager = PersistentSessionManager()
    dispatcher = MethodDispatcher(agent=agent, session_manager=session_manager, server=server)
    server.set_dispatcher(dispatcher)

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
def serve(agent_config: str | None, verbose: bool) -> None:
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

    asyncio.run(_serve(agent_config, verbose))

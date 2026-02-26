"""Sequential pipeline execution of agents."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sage.agent import Agent

logger = logging.getLogger(__name__)


class Pipeline:
    """Sequential pipeline — output of one agent becomes input to the next.

    Usage::

        pipeline = Pipeline([agent1, agent2, agent3])
        result = await pipeline.run("initial input")

    Or using the ``>>`` operator::

        pipeline = agent1 >> agent2 >> agent3
        result = await pipeline.run("initial input")
    """

    def __init__(self, agents: list[Agent]) -> None:
        self.agents = list(agents)

    async def run(self, input: str) -> str:
        """Run the pipeline sequentially, passing output to next agent."""
        logger.debug("Pipeline run: %d steps", len(self.agents))
        current = input
        for i, agent in enumerate(self.agents):
            logger.debug("Pipeline step %d/%d: agent='%s'", i + 1, len(self.agents), agent.name)
            current = await agent.run(current)
        return current

    async def stream(self, input: str) -> AsyncIterator[str]:
        """Stream the pipeline — intermediate agents run(), final agent streams."""
        if not self.agents:
            return
        logger.debug("Pipeline stream: %d steps", len(self.agents))
        current = input
        for i, agent in enumerate(self.agents[:-1]):
            logger.debug(
                "Pipeline stream step %d/%d: agent='%s'", i + 1, len(self.agents), agent.name
            )
            current = await agent.run(current)
        async for chunk in self.agents[-1].stream(current):
            yield chunk

    def __rshift__(self, other: Agent | Pipeline) -> Pipeline:
        """Support ``pipeline >> agent`` and ``pipeline >> pipeline`` syntax."""
        if isinstance(other, Pipeline):
            return Pipeline(self.agents + other.agents)
        return Pipeline(self.agents + [other])

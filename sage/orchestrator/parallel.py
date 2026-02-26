"""Parallel and race execution of multiple agents."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from sage.agent import Agent
from sage.exceptions import SageError

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from a single agent execution."""

    agent_name: str
    output: str
    error: Exception | None = None

    @property
    def success(self) -> bool:
        return self.error is None


class Orchestrator:
    """Orchestrate multiple agents for parallel and competitive execution."""

    @staticmethod
    async def run_parallel(
        agents: list[Agent],
        inputs: list[str] | str,
    ) -> list[AgentResult]:
        """Run multiple agents in parallel using asyncio.gather.

        Args:
            agents: List of agents to run.
            inputs: Either a single input string (same for all agents) or
                    a list of inputs (one per agent, must match length).

        Returns:
            List of AgentResult, one per agent, in same order.
        """
        if isinstance(inputs, str):
            input_list = [inputs] * len(agents)
        else:
            if len(inputs) != len(agents):
                raise SageError(
                    f"Number of inputs ({len(inputs)}) must match number of agents ({len(agents)})"
                )
            input_list = inputs

        logger.info(
            "Parallel run: %d agents [%s]",
            len(agents),
            ", ".join(a.name for a in agents),
        )

        async def _run_one(agent: Agent, inp: str) -> AgentResult:
            try:
                output = await agent.run(inp)
                logger.debug("Subagent '%s' completed successfully", agent.name)
                return AgentResult(agent_name=agent.name, output=output)
            except Exception as exc:
                logger.error("Subagent '%s' failed: %s", agent.name, exc)
                return AgentResult(agent_name=agent.name, output="", error=exc)

        results = await asyncio.gather(
            *(_run_one(agent, inp) for agent, inp in zip(agents, input_list))
        )
        logger.info(
            "Parallel run complete: %d/%d succeeded",
            sum(1 for r in results if r.success),
            len(results),
        )
        return list(results)

    @staticmethod
    async def run_race(
        agents: list[Agent],
        input: str,
    ) -> AgentResult:
        """Run multiple agents competitively — first to complete wins.

        If all agents fail, raises SageError with collected errors.
        """

        async def _run_one(agent: Agent) -> AgentResult:
            try:
                output = await agent.run(input)
                return AgentResult(agent_name=agent.name, output=output)
            except Exception as exc:
                return AgentResult(agent_name=agent.name, output="", error=exc)

        tasks = [asyncio.create_task(_run_one(agent)) for agent in agents]

        errors: list[AgentResult] = []

        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result.success:
                # Cancel remaining tasks.
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)  # Wait for cleanup
                return result
            errors.append(result)

        raise SageError(f"All agents failed: {[f'{e.agent_name}: {e.error}' for e in errors]}")

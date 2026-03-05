from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sage.tools.decorator import tool as _tool

if TYPE_CHECKING:
    from sage.agent import Agent

logger = logging.getLogger(__name__)


def register_skill_tool(agent: "Agent") -> None:
    """Register ``use_skill`` tool when the agent has skills.

    The tool returns a skill's full markdown content on first invocation
    and a short "already loaded" message on subsequent calls for the same
    skill.  This implements two-phase skill loading: only the lightweight
    catalog (name + description) lives in the system prompt; full content
    is loaded on demand.
    """
    if not agent.skills:
        return

    skill_map = {s.name: s for s in agent.skills}
    loaded = agent._loaded_skills

    @_tool
    async def use_skill(name: str) -> str:
        """Load a skill's full instructions by name.

        Use this when a task matches one of the available skills listed
        in your system prompt.  Returns the skill's complete markdown
        instructions for you to follow.
        """
        if name not in skill_map:
            available = ", ".join(sorted(skill_map))
            return f"Unknown skill '{name}'. Available: {available}"
        if name in loaded:
            logger.debug("Skill '%s' already loaded, returning cached notice", name)
            return f"Skill '{name}' is already loaded in this conversation."
        loaded.add(name)
        logger.debug("Loaded skill '%s'", name)
        skill = skill_map[name]
        return skill.content

    # Constrain the name parameter to valid skill names.
    use_skill.__tool_schema__.parameters["properties"]["name"]["enum"] = sorted(skill_map)
    agent.tool_registry.register(use_skill)

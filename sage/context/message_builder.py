from __future__ import annotations

from typing import TYPE_CHECKING

from sage.models import Message

if TYPE_CHECKING:
    from sage.agent import Agent


def build_system_message(agent: "Agent") -> str:
    system_parts: list[str] = []
    if agent._body:
        from sage.prompts.dynamic_builder import resolve_placeholder

        resolved_body = resolve_placeholder(agent._body, agent.subagents)
        system_parts.append(resolved_body)
    if agent._identity_prompt:
        system_parts.append(agent._identity_prompt)
    if agent.skills:
        catalog_lines = [
            "## Available Skills",
            "Use the `use_skill` tool to load a skill's full instructions.",
            "",
        ]
        for skill in agent.skills:
            line = f"- **{skill.name}**"
            if skill.description:
                line += f": {skill.description}"
            catalog_lines.append(line)
        system_parts.append("\n".join(catalog_lines))

    base_prompt = "\n\n".join(system_parts)

    from sage.prompts.overlays import registry as overlay_registry

    return overlay_registry.apply(agent.model, base_prompt)


def build_messages(agent: "Agent", input: str, memory_context: str | None = None) -> list[Message]:
    messages: list[Message] = []

    system_content = build_system_message(agent)
    if system_content:
        messages.append(Message(role="system", content=system_content))

    if memory_context:
        messages.append(Message(role="system", content=f"[Relevant memory]\n{memory_context}"))

    messages.extend(agent._conversation_history)

    messages.append(Message(role="user", content=input))
    return messages

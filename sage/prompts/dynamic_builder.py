from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sage.agent import Agent

DELEGATION_PLACEHOLDER = "{{DELEGATION_TABLE}}"


def _format_list(items: list[str]) -> str:
    return ", ".join(items) if items else "—"


def build_delegation_table(subagents: Mapping[str, Agent]) -> str:
    if not subagents:
        return ""

    rows: list[str] = []
    rows.append("| Agent | Cost | Description | Use When | Avoid When | Triggers |")
    rows.append("|-------|------|-------------|----------|------------|----------|")

    for name, agent in sorted(subagents.items()):
        meta = getattr(agent, "_prompt_metadata", None)
        desc = agent.description or "—"
        if meta is None:
            rows.append(f"| **{name}** | — | {desc} | — | — | — |")
            continue

        cost = meta.cost
        use_when = _format_list(meta.use_when)
        avoid_when = _format_list(meta.avoid_when)
        triggers = _format_list(meta.triggers)
        rows.append(f"| **{name}** | {cost} | {desc} | {use_when} | {avoid_when} | {triggers} |")

    return "\n".join(rows)


def build_orchestrator_prompt(subagents: Mapping[str, Agent]) -> str:
    table = build_delegation_table(subagents)
    if not table:
        return ""

    return (
        "## Available Agents\n\n"
        "Use the `delegate` or `delegate_background` tools to assign work.\n\n"
        f"{table}"
    )


def resolve_placeholder(body: str, subagents: Mapping[str, Agent]) -> str:
    if DELEGATION_PLACEHOLDER not in body:
        return body
    return body.replace(DELEGATION_PLACEHOLDER, build_orchestrator_prompt(subagents))

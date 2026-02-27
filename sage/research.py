"""Configurable pre-response information gathering phase."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from sage.models import Message

if TYPE_CHECKING:
    from sage.providers.base import ProviderProtocol
    from sage.tools.registry import ToolRegistry

_QUESTION_WORDS = ("who", "what", "where", "when", "why", "how")

_RESEARCH_SYSTEM_PROMPT = (
    "Gather information to help answer the following query. "
    "Use available tools. "
    "When done, output [RESEARCH COMPLETE] followed by your findings."
)

_RESEARCH_SENTINEL = "[RESEARCH COMPLETE]"


class ResearchTrigger(str, Enum):
    """Conditions under which the research phase is triggered."""

    NEVER = "never"
    ALWAYS = "always"
    KEYWORDS = "keywords"
    LENGTH = "length"
    QUESTION = "question"


class ResearchConfig(BaseModel):
    """Configuration for the pre-response research phase."""

    trigger: ResearchTrigger = ResearchTrigger.NEVER
    keywords: list[str] = []
    min_length: int = 100
    max_turns: int = 3
    tools: list[str] = []


def should_research(query: str, config: ResearchConfig) -> bool:
    """Determine whether the research phase should run for this query.

    Args:
        query: The user query string.
        config: Research configuration controlling when research triggers.

    Returns:
        True if research should be performed, False otherwise.
    """
    trigger = config.trigger

    if trigger == ResearchTrigger.NEVER:
        return False

    if trigger == ResearchTrigger.ALWAYS:
        return True

    if trigger == ResearchTrigger.KEYWORDS:
        query_lower = query.lower()
        return any(kw.lower() in query_lower for kw in config.keywords)

    if trigger == ResearchTrigger.LENGTH:
        return len(query) > config.min_length

    if trigger == ResearchTrigger.QUESTION:
        stripped = query.strip()
        if stripped.endswith("?"):
            return True
        first_word = stripped.split()[0].lower() if stripped else ""
        return first_word in _QUESTION_WORDS

    return False


async def run_research(
    query: str,
    config: ResearchConfig,
    tool_registry: "ToolRegistry",
    provider: "ProviderProtocol",
) -> str:
    """Run the pre-response research phase as a mini agent loop.

    Sends the query to the provider with a research-focused system prompt,
    executes any tool calls, and repeats until either the sentinel
    ``[RESEARCH COMPLETE]`` appears in the response or ``max_turns`` is
    exceeded.

    Args:
        query: The user query to research.
        config: Research configuration including max_turns and tool list.
        tool_registry: Registry used to look up and execute tool calls.
        provider: LLM provider used for completions.

    Returns:
        The text after ``[RESEARCH COMPLETE]`` if the sentinel was found,
        otherwise the last response text.
    """
    messages: list[Message] = [
        Message(role="system", content=_RESEARCH_SYSTEM_PROMPT),
        Message(role="user", content=query),
    ]

    tool_schemas = tool_registry.get_schemas() or None
    last_content = ""

    for _turn in range(config.max_turns):
        result = await provider.complete(messages, tools=tool_schemas)
        assistant_message = result.message
        messages.append(assistant_message)

        content = assistant_message.content or ""
        last_content = content

        # Check for sentinel before processing tool calls so we return
        # immediately when the model signals it is done.
        if _RESEARCH_SENTINEL in content:
            idx = content.index(_RESEARCH_SENTINEL) + len(_RESEARCH_SENTINEL)
            return content[idx:].strip()

        # Execute any tool calls and feed results back for the next turn.
        if assistant_message.tool_calls:
            for tc in assistant_message.tool_calls:
                try:
                    tool_result = await tool_registry.execute(tc.name, tc.arguments)
                except Exception as exc:
                    tool_result = f"Error executing tool '{tc.name}': {exc}"

                messages.append(
                    Message(
                        role="tool",
                        content=str(tool_result),
                        tool_call_id=tc.id,
                    )
                )

    return last_content

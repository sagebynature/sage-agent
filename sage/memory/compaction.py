"""Message compaction via LLM summarisation."""

from __future__ import annotations

import logging

from sage.models import Message
from sage.providers.base import ProviderProtocol

logger = logging.getLogger(__name__)


async def compact_messages(
    messages: list[Message],
    provider: ProviderProtocol,
    threshold: int = 50,
    keep_recent: int = 10,
) -> list[Message]:
    """Compact *messages* when they exceed *threshold*.

    Strategy:
      1. Preserve any system messages at their original positions.
      2. Summarise the oldest non-system messages using the *provider*.
      3. Keep the most recent *keep_recent* non-system messages verbatim.
    """
    if len(messages) <= threshold:
        logger.debug(
            "Compaction skipped: message count %d <= threshold %d",
            len(messages),
            threshold,
        )
        return messages

    system_msgs = [m for m in messages if m.role == "system"]
    non_system = [m for m in messages if m.role != "system"]

    if len(non_system) <= keep_recent:
        logger.debug(
            "Compaction skipped: non-system messages %d <= keep_recent %d",
            len(non_system),
            keep_recent,
        )
        return messages

    to_summarize = non_system[:-keep_recent]
    to_keep = non_system[-keep_recent:]

    logger.info(
        "Compaction triggered: summarizing %d message(s), keeping %d recent",
        len(to_summarize),
        len(to_keep),
    )

    summary_text = "\n".join(f"{m.role}: {m.content or '[tool call]'}" for m in to_summarize)

    summary_result = await provider.complete(
        [
            Message(
                role="system",
                content="Summarize this conversation concisely, preserving key facts and decisions.",
            ),
            Message(role="user", content=summary_text),
        ]
    )

    summary_msg = Message(
        role="system",
        content=f"[Conversation summary]: {summary_result.message.content}",
    )

    compacted = system_msgs + [summary_msg] + to_keep
    logger.info(
        "Compaction complete: before=%d, after=%d",
        len(messages),
        len(compacted),
    )
    return compacted


def prune_tool_outputs(
    messages: list[Message],
    max_chars: int = 5000,
    keep_recent: int = 10,
) -> list[Message]:
    """Truncate large tool outputs in older messages.

    Tool messages beyond the last *keep_recent* messages that exceed
    *max_chars* are replaced with a truncation notice preserving the
    first *max_chars* characters.
    """
    if not messages:
        return messages

    cutoff = max(0, len(messages) - keep_recent)
    result: list[Message] = []
    truncated_count = 0

    for i, msg in enumerate(messages):
        if i < cutoff and msg.role == "tool" and msg.content and len(msg.content) > max_chars:
            truncated = (
                msg.content[:max_chars] + f"\n\n[Truncated — original was {len(msg.content)} chars]"
            )
            result.append(msg.model_copy(update={"content": truncated}))
            truncated_count += 1
        else:
            result.append(msg)

    if truncated_count:
        logger.debug("Pruned %d oversized tool output(s)", truncated_count)
    return result

"""Message compaction via LLM summarisation."""

from __future__ import annotations

import logging

from sage.models import Message
from sage.providers.base import ProviderProtocol

logger = logging.getLogger(__name__)

MAX_SUMMARY_CHARS: int = 2000
MAX_SOURCE_CHARS: int = 12000
MAX_BULLET_POINTS: int = 12


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

    # Serialize messages to text; drop oldest first if it exceeds MAX_SOURCE_CHARS
    candidates = list(to_summarize)
    summary_text = "\n".join(f"{m.role}: {m.content or '[tool call]'}" for m in candidates)
    if len(summary_text) > MAX_SOURCE_CHARS:
        logger.warning(
            "Source text (%d chars) exceeds MAX_SOURCE_CHARS (%d); truncating oldest messages",
            len(summary_text),
            MAX_SOURCE_CHARS,
        )
        while candidates and len(summary_text) > MAX_SOURCE_CHARS:
            candidates.pop(0)
            summary_text = "\n".join(f"{m.role}: {m.content or '[tool call]'}" for m in candidates)

    summary_result = await provider.complete(
        [
            Message(
                role="system",
                content=(
                    "Summarize the conversation as a bulleted list with at most "
                    f"{MAX_BULLET_POINTS} items. "
                    "Each bullet point should start with '- ' and be a single concise statement. "
                    f"Total output must be under {MAX_SUMMARY_CHARS} characters."
                ),
            ),
            Message(role="user", content=summary_text),
        ]
    )

    raw_summary = summary_result.message.content or ""

    # Post-process: enforce MAX_SUMMARY_CHARS by truncating at the last complete bullet
    if len(raw_summary) > MAX_SUMMARY_CHARS:
        logger.warning(
            "LLM summary (%d chars) exceeds MAX_SUMMARY_CHARS (%d); truncating",
            len(raw_summary),
            MAX_SUMMARY_CHARS,
        )
        # Find all bullet lines and keep as many as fit within the limit
        lines = raw_summary.splitlines(keepends=True)
        truncated_lines: list[str] = []
        total = 0
        last_bullet_end = 0
        for line in lines:
            if total + len(line) > MAX_SUMMARY_CHARS:
                break
            truncated_lines.append(line)
            total += len(line)
            stripped = line.lstrip()
            if stripped.startswith("- ") or stripped.startswith("* "):
                last_bullet_end = len(truncated_lines)

        # Use up to the last complete bullet point if we found any
        if last_bullet_end > 0:
            raw_summary = "".join(truncated_lines[:last_bullet_end]).rstrip()
        else:
            # No bullet points found — hard truncate
            raw_summary = raw_summary[:MAX_SUMMARY_CHARS]

    summary_msg = Message(
        role="system",
        content=f"[Conversation summary]: {raw_summary}",
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

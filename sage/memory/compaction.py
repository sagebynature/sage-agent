"""Message compaction via LLM summarisation."""

from __future__ import annotations

import logging
from typing import Protocol

from sage.models import Message
from sage.providers.base import ProviderProtocol

logger = logging.getLogger(__name__)

MAX_SUMMARY_CHARS: int = 2000
MAX_SOURCE_CHARS: int = 12000
MAX_BULLET_POINTS: int = 12


class CompactionController(Protocol):
    async def compact(
        self,
        messages: list[Message],
        *,
        provider: ProviderProtocol,
    ) -> list[Message]: ...


class DefaultCompactionController:
    def __init__(
        self,
        *,
        threshold: int = 50,
        keep_recent: int = 10,
        max_summary_chars: int = MAX_SUMMARY_CHARS,
        max_source_chars: int = MAX_SOURCE_CHARS,
        max_bullet_points: int = MAX_BULLET_POINTS,
    ) -> None:
        self.threshold = threshold
        self.keep_recent = keep_recent
        self.max_summary_chars = max_summary_chars
        self.max_source_chars = max_source_chars
        self.max_bullet_points = max_bullet_points

    async def compact(
        self,
        messages: list[Message],
        *,
        provider: ProviderProtocol,
    ) -> list[Message]:
        return await compact_messages(
            messages,
            provider=provider,
            threshold=self.threshold,
            keep_recent=self.keep_recent,
            max_summary_chars=self.max_summary_chars,
            max_source_chars=self.max_source_chars,
            max_bullet_points=self.max_bullet_points,
        )


class NullCompactionController:
    async def compact(
        self,
        messages: list[Message],
        *,
        provider: ProviderProtocol | None = None,
    ) -> list[Message]:
        _ = provider
        return messages


async def compact_messages(
    messages: list[Message],
    provider: ProviderProtocol,
    threshold: int = 50,
    keep_recent: int = 10,
    max_summary_chars: int = MAX_SUMMARY_CHARS,
    max_source_chars: int = MAX_SOURCE_CHARS,
    max_bullet_points: int = MAX_BULLET_POINTS,
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

    # Serialize messages to text; drop oldest first if it exceeds max_source_chars
    candidates = list(to_summarize)
    summary_text = "\n".join(f"{m.role}: {m.content or '[tool call]'}" for m in candidates)
    if len(summary_text) > max_source_chars:
        logger.warning(
            "Source text (%d chars) exceeds MAX_SOURCE_CHARS (%d); truncating oldest messages",
            len(summary_text),
            max_source_chars,
        )
        while candidates and len(summary_text) > max_source_chars:
            candidates.pop(0)
            summary_text = "\n".join(f"{m.role}: {m.content or '[tool call]'}" for m in candidates)

    summary_result = await provider.complete(
        [
            Message(
                role="system",
                content=(
                    "Summarize the conversation as a bulleted list with at most "
                    f"{max_bullet_points} items. "
                    "Each bullet point should start with '- ' and be a single concise statement. "
                    f"Total output must be under {max_summary_chars} characters."
                ),
            ),
            Message(role="user", content=summary_text),
        ]
    )

    raw_summary = summary_result.message.content or ""

    # Post-process: enforce max_summary_chars by truncating at the last complete bullet
    if len(raw_summary) > max_summary_chars:
        logger.warning(
            "LLM summary (%d chars) exceeds MAX_SUMMARY_CHARS (%d); truncating",
            len(raw_summary),
            max_summary_chars,
        )
        lines = raw_summary.splitlines(keepends=True)
        truncated_lines: list[str] = []
        total = 0
        last_bullet_end = 0
        for line in lines:
            if total + len(line) > max_summary_chars:
                break
            truncated_lines.append(line)
            total += len(line)
            stripped = line.lstrip()
            if stripped.startswith("- ") or stripped.startswith("* "):
                last_bullet_end = len(truncated_lines)

        if last_bullet_end > 0:
            raw_summary = "".join(truncated_lines[:last_bullet_end]).rstrip()
        else:
            raw_summary = raw_summary[:max_summary_chars]

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


async def multi_part_compact(
    messages: list[Message],
    provider: "ProviderProtocol",
    *,
    max_chunk_chars: int = 12000,
    _depth: int = 0,
) -> list[Message]:
    """Multi-part summarization: split large histories, summarize chunks, merge.

    If total content <= max_chunk_chars: delegate to compact_messages() (single-pass).
    Otherwise: split → summarize each chunk → merge → final compact. Max depth 3.
    """
    MAX_DEPTH = 3
    total_chars = sum(len(m.content or "") for m in messages)

    if total_chars <= max_chunk_chars or _depth >= MAX_DEPTH:
        return await compact_messages(messages, provider)

    chunks = _split_into_chunks(messages, max_chunk_chars)
    summaries: list[Message] = []
    for chunk in chunks:
        chunk_result = await compact_messages(chunk, provider)
        summaries.extend(chunk_result)

    merged_chars = sum(len(m.content or "") for m in summaries)
    if merged_chars > max_chunk_chars and _depth < MAX_DEPTH:
        return await multi_part_compact(
            summaries, provider, max_chunk_chars=max_chunk_chars, _depth=_depth + 1
        )
    return await compact_messages(summaries, provider)


def _split_into_chunks(messages: list[Message], max_chunk_chars: int) -> list[list[Message]]:
    """Split messages into chunks of <= max_chunk_chars at message boundaries."""
    chunks: list[list[Message]] = []
    current_chunk: list[Message] = []
    current_size = 0
    for msg in messages:
        msg_size = len(msg.content or "")
        if current_chunk and current_size + msg_size > max_chunk_chars:
            chunks.append(current_chunk)
            current_chunk = [msg]
            current_size = msg_size
        else:
            current_chunk.append(msg)
            current_size += msg_size
    if current_chunk:
        chunks.append(current_chunk)
    return chunks if chunks else [messages]


def emergency_drop(messages: list[Message], *, keep_last_n: int = 5) -> list[Message]:
    """Nuclear fallback: drop oldest messages preserving system/last-user/tool-results.

    Never drops system messages, the most recent user message, or tool results.
    Keeps protected messages + last keep_last_n non-protected messages.
    """
    if not messages:
        return messages
    last_user_idx: int | None = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].role == "user":
            last_user_idx = i
            break
    protected: set[int] = set()
    for i, msg in enumerate(messages):
        if msg.role == "system":
            protected.add(i)
        if i == last_user_idx:
            protected.add(i)
        if getattr(msg, "tool_call_id", None) or msg.role == "tool":
            protected.add(i)
    non_protected = [(i, msg) for i, msg in enumerate(messages) if i not in protected]
    keep_non_protected = {i for i, _ in non_protected[-keep_last_n:]} if non_protected else set()
    keep = protected | keep_non_protected
    result = [msg for i, msg in enumerate(messages) if i in keep]
    dropped = len(messages) - len(result)
    if dropped > 0:
        logger.warning("Emergency drop: removed %d messages, kept %d", dropped, len(result))
    return result


def deterministic_trim(messages: list[Message], *, target_count: int = 20) -> list[Message]:
    """Simple trim: drop oldest non-system messages to reach target_count.

    Preserves system messages. No LLM calls.
    """
    if len(messages) <= target_count:
        return messages
    system_msgs = [m for m in messages if m.role == "system"]
    non_system = [m for m in messages if m.role != "system"]
    keep_count = max(0, target_count - len(system_msgs))
    kept_non_system = non_system[-keep_count:] if keep_count > 0 else []
    kept_set = {id(m) for m in system_msgs + kept_non_system}
    result = [m for m in messages if id(m) in kept_set]
    dropped = len(messages) - len(result)
    if dropped > 0:
        logger.info(
            "Deterministic trim: reduced from %d to %d messages", len(messages), len(result)
        )
    return result


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

"""Tests for message compaction."""

from __future__ import annotations

from typing import Literal
from unittest.mock import AsyncMock, patch

import pytest

from sage.memory.compaction import (
    MAX_BULLET_POINTS,
    MAX_SOURCE_CHARS,
    MAX_SUMMARY_CHARS,
    NullCompactionController,
    compact_messages,
    prune_tool_outputs,
)
from sage.models import CompletionResult, Message, Usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _msg(role: Literal["system", "user", "assistant", "tool"], content: str) -> Message:
    return Message(role=role, content=content)


def _make_provider(summary_text: str = "Summary of earlier conversation.") -> AsyncMock:
    """Return a mock provider whose ``complete`` returns *summary_text*."""
    provider = AsyncMock()
    provider.complete.return_value = CompletionResult(
        message=Message(role="assistant", content=summary_text),
        usage=Usage(),
    )
    return provider


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCompactMessagesBelowThreshold:
    @pytest.mark.asyncio
    async def test_returns_unchanged_when_below_threshold(self) -> None:
        msgs = [_msg("user", f"msg {i}") for i in range(10)]
        provider = _make_provider()
        result = await compact_messages(msgs, provider, threshold=50)
        assert result is msgs
        provider.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_unchanged_at_exact_threshold(self) -> None:
        msgs = [_msg("user", f"msg {i}") for i in range(50)]
        provider = _make_provider()
        result = await compact_messages(msgs, provider, threshold=50)
        assert result is msgs


class TestCompactMessagesAboveThreshold:
    @pytest.mark.asyncio
    async def test_compacts_when_above_threshold(self) -> None:
        msgs = [_msg("user", f"msg {i}") for i in range(60)]
        provider = _make_provider("Condensed history.")
        result = await compact_messages(msgs, provider, threshold=50, keep_recent=10)

        # Should have the summary message + 10 recent
        assert len(result) == 11
        assert result[0].role == "system"
        assert "[Conversation summary]" in (result[0].content or "")
        assert "Condensed history." in (result[0].content or "")
        provider.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_preserves_system_message(self) -> None:
        system = _msg("system", "You are helpful.")
        non_system = [_msg("user", f"msg {i}") for i in range(55)]
        msgs = [system] + non_system

        provider = _make_provider()
        result = await compact_messages(msgs, provider, threshold=50, keep_recent=10)

        # Original system message + summary + 10 recent
        assert result[0] == system
        assert result[1].role == "system"
        assert "[Conversation summary]" in (result[1].content or "")
        assert len(result) == 12

    @pytest.mark.asyncio
    async def test_preserves_recent_messages(self) -> None:
        msgs = [_msg("user", f"msg {i}") for i in range(60)]
        provider = _make_provider()
        result = await compact_messages(msgs, provider, threshold=50, keep_recent=10)

        recent_contents = [m.content for m in result[-10:]]
        expected = [f"msg {i}" for i in range(50, 60)]
        assert recent_contents == expected

    @pytest.mark.asyncio
    async def test_no_compaction_when_non_system_below_keep_recent(self) -> None:
        system_msgs = [_msg("system", f"sys {i}") for i in range(45)]
        non_system = [_msg("user", f"msg {i}") for i in range(8)]
        msgs = system_msgs + non_system

        provider = _make_provider()
        result = await compact_messages(msgs, provider, threshold=50)
        # Total > threshold but non-system <= keep_recent → no compaction
        assert result is msgs
        provider.complete.assert_not_called()


class TestCompactMessagesSummaryPrompt:
    @pytest.mark.asyncio
    async def test_summary_prompt_contains_old_messages(self) -> None:
        msgs = [_msg("user", f"important fact {i}") for i in range(60)]
        provider = _make_provider()
        await compact_messages(msgs, provider, threshold=50, keep_recent=10)

        call_args = provider.complete.call_args[0][0]
        # The user message should contain the old messages
        user_prompt = call_args[1].content
        assert "important fact 0" in user_prompt
        assert "important fact 49" in user_prompt
        # Recent messages should not be in the summary prompt
        assert "important fact 50" not in user_prompt


class TestNullCompactionController:
    @pytest.mark.asyncio
    async def test_returns_messages_unchanged(self) -> None:
        messages = [_msg("user", "hello"), _msg("assistant", "hi")]
        controller = NullCompactionController()

        result = await controller.compact(messages, provider=None)

        assert result is messages


# ---------------------------------------------------------------------------
# Tool output pruning tests
# ---------------------------------------------------------------------------


class TestPruneToolOutputs:
    def test_truncates_long_tool_output(self) -> None:
        long_content = "x" * 10000
        msgs = [
            _msg("user", "hello"),
            _msg("assistant", "calling tool"),
            Message(role="tool", content=long_content, tool_call_id="1"),
            _msg("user", "thanks"),
        ]
        pruned = prune_tool_outputs(msgs, max_chars=5000, keep_recent=1)
        assert len(pruned[2].content or "") < 6000
        assert "[truncated" in (pruned[2].content or "").lower()

    def test_preserves_short_tool_output(self) -> None:
        msgs = [
            Message(role="tool", content="short output", tool_call_id="1"),
        ]
        pruned = prune_tool_outputs(msgs, max_chars=5000)
        assert pruned[0].content == "short output"

    def test_preserves_recent_tool_outputs(self) -> None:
        """Tool outputs in the last keep_recent messages should not be pruned."""
        long_content = "y" * 10000
        msgs = [
            _msg("user", "old"),
            Message(role="tool", content=long_content, tool_call_id="1"),
            _msg("user", "recent"),
            Message(role="tool", content=long_content, tool_call_id="2"),
        ]
        # Only prune the first tool output (keep_recent=2 means last 2 preserved).
        pruned = prune_tool_outputs(msgs, max_chars=5000, keep_recent=2)
        assert "[truncated" in (pruned[1].content or "").lower()
        assert pruned[3].content == long_content  # recent — preserved


# ---------------------------------------------------------------------------
# Character caps and bullet-point format tests (Task 14)
# ---------------------------------------------------------------------------


class TestConstants:
    def test_max_summary_constant(self) -> None:
        assert MAX_SUMMARY_CHARS == 2000

    def test_source_truncation_constant(self) -> None:
        assert MAX_SOURCE_CHARS == 12000

    def test_max_bullet_constant(self) -> None:
        assert MAX_BULLET_POINTS == 12


class TestSummaryCharLimit:
    @pytest.mark.asyncio
    async def test_summary_char_limit_respected(self) -> None:
        """If the LLM returns a summary >2000 chars, it must be truncated to <=2000."""
        # Build a mock response that exceeds MAX_SUMMARY_CHARS
        long_summary = "- " + "x" * 2500  # single bullet, way over limit
        provider = _make_provider(long_summary)

        msgs = [_msg("user", f"msg {i}") for i in range(60)]
        result = await compact_messages(msgs, provider, threshold=50, keep_recent=10)

        # Find the summary message (system role containing [Conversation summary])
        summary_msg = next(
            m
            for m in result
            if m.role == "system" and "[Conversation summary]" in (m.content or "")
        )
        assert len(summary_msg.content or "") <= MAX_SUMMARY_CHARS + len("[Conversation summary]: ")

    @pytest.mark.asyncio
    async def test_bullet_point_truncation(self) -> None:
        """When LLM returns many bullets, output is truncated at last complete bullet <=2000 chars."""
        # Create a response with many bullet points that together exceed 2000 chars
        # Each bullet is ~100 chars, so 25 bullets = ~2500 chars
        bullets = [f"- Bullet point number {i:03d}: " + "detail " * 10 for i in range(25)]
        long_summary = "\n".join(bullets)
        provider = _make_provider(long_summary)

        msgs = [_msg("user", f"msg {i}") for i in range(60)]
        result = await compact_messages(msgs, provider, threshold=50, keep_recent=10)

        summary_msg = next(
            m
            for m in result
            if m.role == "system" and "[Conversation summary]" in (m.content or "")
        )
        content = summary_msg.content or ""
        # Total content must be within limit
        assert len(content) <= MAX_SUMMARY_CHARS + len("[Conversation summary]: ")
        # The raw summary part (after "[Conversation summary]: ") must be at most MAX_SUMMARY_CHARS
        raw_summary = content.removeprefix("[Conversation summary]: ")
        assert len(raw_summary) <= MAX_SUMMARY_CHARS

    @pytest.mark.asyncio
    async def test_short_summary_not_truncated(self) -> None:
        """A summary within the limit is returned as-is."""
        short_summary = "- Point A.\n- Point B.\n- Point C."
        provider = _make_provider(short_summary)

        msgs = [_msg("user", f"msg {i}") for i in range(60)]
        result = await compact_messages(msgs, provider, threshold=50, keep_recent=10)

        summary_msg = next(
            m
            for m in result
            if m.role == "system" and "[Conversation summary]" in (m.content or "")
        )
        assert short_summary in (summary_msg.content or "")


class TestSourceTruncation:
    @pytest.mark.asyncio
    async def test_source_truncated_when_exceeds_max(self) -> None:
        """When the serialized source text exceeds MAX_SOURCE_CHARS, oldest messages are dropped."""
        # Create messages with large content so they exceed MAX_SOURCE_CHARS when serialized
        # Each message is ~600 chars; 25 messages = ~15000 chars > 12000
        large_msgs = [_msg("user", f"msg_{i}: " + "A" * 600) for i in range(25)]
        # Add more recent messages to keep
        recent_msgs = [_msg("user", f"recent {i}") for i in range(10)]
        all_msgs = large_msgs + recent_msgs

        provider = _make_provider("Summary.")
        await compact_messages(all_msgs, provider, threshold=10, keep_recent=10)

        # The provider should have been called with source text <= MAX_SOURCE_CHARS
        call_args = provider.complete.call_args[0][0]
        user_prompt = call_args[1].content or ""
        assert len(user_prompt) <= MAX_SOURCE_CHARS

    @pytest.mark.asyncio
    async def test_source_within_limit_not_truncated(self) -> None:
        """When source text is within MAX_SOURCE_CHARS, all messages are included."""
        # Small messages that won't exceed the limit
        msgs = [_msg("user", f"msg {i}") for i in range(60)]
        provider = _make_provider()
        await compact_messages(msgs, provider, threshold=50, keep_recent=10)

        call_args = provider.complete.call_args[0][0]
        user_prompt = call_args[1].content or ""
        # All 50 to-summarize messages should be present
        assert "msg 0" in user_prompt
        assert "msg 49" in user_prompt


class TestSystemPromptBulletFormat:
    @pytest.mark.asyncio
    async def test_system_prompt_requests_bullet_points(self) -> None:
        """The system prompt sent to the LLM should request bullet-point format."""
        msgs = [_msg("user", f"msg {i}") for i in range(60)]
        provider = _make_provider()
        await compact_messages(msgs, provider, threshold=50, keep_recent=10)

        call_args = provider.complete.call_args[0][0]
        system_prompt = call_args[0].content or ""
        # Check that the system prompt mentions bullet points
        assert "bullet" in system_prompt.lower() or "- " in system_prompt


# ---------------------------------------------------------------------------
# Task 17: multi_part_compact tests
# ---------------------------------------------------------------------------


class TestMultiPartCompactImportable:
    def test_multi_part_compact_importable(self) -> None:
        from sage.memory.compaction import multi_part_compact  # noqa: F401

        assert callable(multi_part_compact)


class TestSplitIntoChunks:
    def test_split_into_chunks_importable(self) -> None:
        from sage.memory.compaction import _split_into_chunks  # noqa: F401

        assert callable(_split_into_chunks)

    def test_split_into_chunks_single_chunk_when_small(self) -> None:
        from sage.memory.compaction import _split_into_chunks

        msgs = [_msg("user", "a" * 100), _msg("assistant", "b" * 100)]
        chunks = _split_into_chunks(msgs, max_chunk_chars=1000)
        assert len(chunks) == 1
        assert chunks[0] == msgs

    def test_split_into_chunks_splits_at_boundaries(self) -> None:
        from sage.memory.compaction import _split_into_chunks

        # Each message is 500 chars; max_chunk_chars=600 → each chunk holds 1 msg
        msgs = [_msg("user", "x" * 500) for _ in range(4)]
        chunks = _split_into_chunks(msgs, max_chunk_chars=600)
        assert len(chunks) == 4
        for chunk in chunks:
            assert len(chunk) == 1

    def test_split_into_chunks_groups_fitting_messages(self) -> None:
        from sage.memory.compaction import _split_into_chunks

        # Messages: 300, 300, 300 chars; max=650 → chunk1=[0,1], chunk2=[2]
        msgs = [_msg("user", "y" * 300), _msg("assistant", "y" * 300), _msg("user", "y" * 300)]
        chunks = _split_into_chunks(msgs, max_chunk_chars=650)
        assert len(chunks) == 2
        assert len(chunks[0]) == 2
        assert len(chunks[1]) == 1

    def test_split_into_chunks_empty_returns_single_chunk(self) -> None:
        from sage.memory.compaction import _split_into_chunks

        chunks = _split_into_chunks([], max_chunk_chars=1000)
        assert chunks == [[]]

    def test_split_into_chunks_none_content_treated_as_zero(self) -> None:
        from sage.memory.compaction import _split_into_chunks

        msgs = [Message(role="assistant", content=None), _msg("user", "hello")]
        chunks = _split_into_chunks(msgs, max_chunk_chars=100)
        # None content is 0 chars; both fit in one chunk
        assert len(chunks) == 1


class TestMultiPartCompactSmallHistory:
    @pytest.mark.asyncio
    async def test_small_history_single_pass(self) -> None:
        """Messages fitting within one chunk → compact_messages called once."""
        msgs = [_msg("user", "hi")]
        with patch(
            "sage.memory.compaction.compact_messages", new_callable=AsyncMock
        ) as mock_compact:
            mock_compact.return_value = [_msg("system", "- Summary")]
            from sage.memory.compaction import multi_part_compact

            provider = _make_provider()
            await multi_part_compact(msgs, provider, max_chunk_chars=10000)
            mock_compact.assert_called_once()

    @pytest.mark.asyncio
    async def test_large_history_multiple_chunks(self) -> None:
        """Messages exceeding max_chunk_chars → compact_messages called per chunk + final."""
        # 3 messages of 500 chars each = 1500 total; max_chunk=600 → 3 chunks
        msgs = [_msg("user", "x" * 500) for _ in range(3)]
        call_count = 0

        async def fake_compact(messages, provider, **kwargs):
            nonlocal call_count
            call_count += 1
            return [_msg("system", f"summary-{call_count}")]

        with patch("sage.memory.compaction.compact_messages", side_effect=fake_compact):
            from sage.memory.compaction import multi_part_compact

            provider = _make_provider()
            await multi_part_compact(msgs, provider, max_chunk_chars=600)
            # 3 chunk summaries + 1 final merge pass = 4 calls
            assert call_count >= 4

    @pytest.mark.asyncio
    async def test_depth_limit_respected(self) -> None:
        """Recursion stops at _depth >= MAX_DEPTH=3, falls back to compact_messages."""
        msgs = [_msg("user", "x" * 500)]
        call_count = 0

        async def fake_compact(messages, provider, **kwargs):
            nonlocal call_count
            call_count += 1
            # Return a large merged message to encourage recursion
            return [_msg("user", "x" * 500)]

        with patch("sage.memory.compaction.compact_messages", side_effect=fake_compact):
            from sage.memory.compaction import multi_part_compact

            provider = _make_provider()
            # Force recursion: pass _depth=3 directly (depth limit)
            await multi_part_compact(msgs, provider, max_chunk_chars=100, _depth=3)
            # At depth 3, should fall through to single compact_messages call
            assert call_count == 1


# ---------------------------------------------------------------------------
# Task 18: emergency_drop tests
# ---------------------------------------------------------------------------


class TestEmergencyDropImportable:
    def test_emergency_drop_importable(self) -> None:
        from sage.memory.compaction import emergency_drop  # noqa: F401

        assert callable(emergency_drop)


class TestEmergencyDrop:
    def test_system_message_preserved(self) -> None:
        from sage.memory.compaction import emergency_drop

        msgs = [
            _msg("system", "You are helpful"),
            _msg("user", "old question"),
            _msg("assistant", "old answer"),
            _msg("user", "latest question"),
        ]
        result = emergency_drop(msgs, keep_last_n=0)
        roles = [m.role for m in result]
        assert "system" in roles
        assert result[0].content == "You are helpful"

    def test_last_user_message_preserved(self) -> None:
        from sage.memory.compaction import emergency_drop

        msgs = [
            _msg("user", "old question 1"),
            _msg("assistant", "old answer 1"),
            _msg("user", "latest question"),
        ]
        result = emergency_drop(msgs, keep_last_n=0)
        contents = [m.content for m in result]
        assert "latest question" in contents

    def test_oldest_dropped_first(self) -> None:
        from sage.memory.compaction import emergency_drop

        msgs = [
            _msg("user", "old 1"),
            _msg("assistant", "old 2"),
            _msg("user", "old 3"),
            _msg("assistant", "old 4"),
            _msg("user", "latest"),
        ]
        # keep_last_n=1 non-protected: should keep only 1 non-protected besides last user
        result = emergency_drop(msgs, keep_last_n=1)
        contents = [m.content for m in result]
        # Latest user is always kept
        assert "latest" in contents
        # Oldest should be dropped
        assert "old 1" not in contents

    def test_keep_last_n_respected(self) -> None:
        from sage.memory.compaction import emergency_drop

        msgs = [
            _msg("user", "old 1"),
            _msg("assistant", "old 2"),
            _msg("user", "old 3"),
            _msg("assistant", "old 4"),
            _msg("user", "latest"),
        ]
        result = emergency_drop(msgs, keep_last_n=2)
        # latest user is protected; keep_last_n=2 non-protected kept
        # non-protected: old 1, old 2, old 3, old 4 → keep last 2: old 3, old 4
        # total: old 3, old 4, latest
        assert len(result) == 3

    def test_tool_results_preserved(self) -> None:
        from sage.memory.compaction import emergency_drop

        msgs = [
            _msg("user", "old 1"),
            Message(role="tool", content="tool result", tool_call_id="tc1"),
            _msg("user", "latest"),
        ]
        result = emergency_drop(msgs, keep_last_n=0)
        roles = [m.role for m in result]
        assert "tool" in roles

    def test_already_small_list_nothing_dropped(self) -> None:
        from sage.memory.compaction import emergency_drop

        msgs = [
            _msg("system", "sys"),
            _msg("user", "only user"),
        ]
        result = emergency_drop(msgs, keep_last_n=5)
        assert len(result) == len(msgs)

    def test_empty_list_returns_empty(self) -> None:
        from sage.memory.compaction import emergency_drop

        result = emergency_drop([], keep_last_n=5)
        assert result == []

    def test_multiple_system_messages_all_preserved(self) -> None:
        from sage.memory.compaction import emergency_drop

        msgs = [
            _msg("system", "sys 1"),
            _msg("system", "sys 2"),
            _msg("user", "old"),
            _msg("assistant", "old answer"),
            _msg("user", "latest"),
        ]
        result = emergency_drop(msgs, keep_last_n=0)
        system_contents = [m.content for m in result if m.role == "system"]
        assert "sys 1" in system_contents
        assert "sys 2" in system_contents


# ---------------------------------------------------------------------------
# Task 19: deterministic_trim tests
# ---------------------------------------------------------------------------


class TestDeterministicTrimImportable:
    def test_deterministic_trim_importable(self) -> None:
        from sage.memory.compaction import deterministic_trim  # noqa: F401

        assert callable(deterministic_trim)


class TestDeterministicTrim:
    def test_trim_to_target(self) -> None:
        from sage.memory.compaction import deterministic_trim

        msgs = [_msg("user" if i % 2 == 0 else "assistant", f"msg {i}") for i in range(31)]
        result = deterministic_trim(msgs, target_count=10)
        assert len(result) == 10

    def test_system_preserved_in_trim(self) -> None:
        from sage.memory.compaction import deterministic_trim

        msgs = [_msg("system", "sys")] + [
            _msg("user" if i % 2 == 0 else "assistant", f"msg {i}") for i in range(30)
        ]
        result = deterministic_trim(msgs, target_count=10)
        # System message must be in result
        assert any(m.role == "system" for m in result)
        assert result[0].role == "system"

    def test_already_small_unchanged(self) -> None:
        from sage.memory.compaction import deterministic_trim

        msgs = [_msg("user", f"msg {i}") for i in range(5)]
        result = deterministic_trim(msgs, target_count=10)
        assert result is msgs

    def test_exactly_at_target_unchanged(self) -> None:
        from sage.memory.compaction import deterministic_trim

        msgs = [_msg("user", f"msg {i}") for i in range(10)]
        result = deterministic_trim(msgs, target_count=10)
        assert result is msgs

    def test_target_count_includes_system(self) -> None:
        from sage.memory.compaction import deterministic_trim

        msgs = [_msg("system", "sys")] + [
            _msg("user" if i % 2 == 0 else "assistant", f"msg {i}") for i in range(30)
        ]
        result = deterministic_trim(msgs, target_count=10)
        # Total kept = target_count (system + non-system)
        assert len(result) == 10

    def test_oldest_non_system_dropped_first(self) -> None:
        from sage.memory.compaction import deterministic_trim

        msgs = [_msg("user", f"msg {i}") for i in range(20)]
        result = deterministic_trim(msgs, target_count=5)
        contents = [m.content for m in result]
        # Most recent 5 should be kept
        assert "msg 19" in contents
        assert "msg 15" in contents
        # Oldest should be dropped
        assert "msg 0" not in contents

    def test_no_non_system_to_drop_when_all_system(self) -> None:
        from sage.memory.compaction import deterministic_trim

        msgs = [_msg("system", f"sys {i}") for i in range(5)]
        # target_count=10 → already ≤ target, return unchanged
        result = deterministic_trim(msgs, target_count=10)
        assert result is msgs

    def test_trim_preserves_message_order(self) -> None:
        from sage.memory.compaction import deterministic_trim

        msgs = [_msg("system", "sys")] + [
            _msg("user" if i % 2 == 0 else "assistant", f"msg {i}") for i in range(30)
        ]
        result = deterministic_trim(msgs, target_count=5)
        # Result should be in the original order (system first)
        assert result[0].role == "system"
        # Remaining should be the last 4 non-system in order
        non_sys = [m for m in result if m.role != "system"]
        contents = [m.content for m in non_sys]
        assert contents == ["msg 26", "msg 27", "msg 28", "msg 29"]

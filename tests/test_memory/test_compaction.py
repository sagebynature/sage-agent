"""Tests for message compaction."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from sage.memory.compaction import (
    MAX_BULLET_POINTS,
    MAX_SOURCE_CHARS,
    MAX_SUMMARY_CHARS,
    compact_messages,
    prune_tool_outputs,
)
from sage.models import CompletionResult, Message, Usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _msg(role: str, content: str) -> Message:
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

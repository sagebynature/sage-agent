"""Tests for the action follow-through guardrail hook (TDD)."""

from __future__ import annotations


from sage.hooks.base import HookEvent
from sage.hooks.builtin.follow_through import (
    BAIL_OUT_PATTERNS,
    detect_bail_out,
    make_follow_through_hook,
)


# ---------------------------------------------------------------------------
# detect_bail_out — pattern detection tests
# ---------------------------------------------------------------------------


class TestDetectBailOut:
    """Unit tests for detect_bail_out()."""

    def test_detect_cannot_execute(self) -> None:
        """'I can't execute that command' should be detected."""
        result = detect_bail_out("I can't execute that command")
        assert result is not None

    def test_detect_cannot_execute_full_form(self) -> None:
        """'I cannot execute that command' (no apostrophe) should be detected."""
        result = detect_bail_out("I cannot execute that command")
        assert result is not None

    def test_detect_unable_to(self) -> None:
        """'I'm unable to perform this action' should be detected."""
        result = detect_bail_out("I'm unable to perform this action")
        assert result is not None

    def test_detect_not_able_to(self) -> None:
        """'I'm not able to do that' should be detected."""
        result = detect_bail_out("I'm not able to do that")
        assert result is not None

    def test_detect_let_me_know(self) -> None:
        """'Let me know if you'd like me to proceed' should be detected."""
        result = detect_bail_out("Let me know if you'd like me to proceed")
        assert result is not None

    def test_detect_would_you_like(self) -> None:
        """'Would you like me to do that?' should be detected."""
        result = detect_bail_out("Would you like me to do that?")
        assert result is not None

    def test_no_detect_success_output(self) -> None:
        """'Here is the output of ls -la' should NOT be detected as bail-out."""
        result = detect_bail_out("Here is the output of ls -la")
        assert result is None

    def test_no_detect_file_created(self) -> None:
        """'The file has been created successfully' should NOT be detected."""
        result = detect_bail_out("The file has been created successfully")
        assert result is None

    def test_no_detect_empty_string(self) -> None:
        """Empty string should not be detected as bail-out."""
        result = detect_bail_out("")
        assert result is None

    def test_detect_no_ability(self) -> None:
        """'I don't have the ability to do this' should be detected."""
        result = detect_bail_out("I don't have the ability to do this")
        assert result is not None

    def test_detect_no_access(self) -> None:
        """'I don't have access to that resource' should be detected."""
        result = detect_bail_out("I don't have access to that resource")
        assert result is not None

    def test_detect_cannot_directly(self) -> None:
        """'I cannot directly modify that file' should be detected."""
        result = detect_bail_out("I cannot directly modify that file")
        assert result is not None

    def test_detect_returns_pattern_name(self) -> None:
        """detect_bail_out should return the pattern name string, not just any truthy value."""
        result = detect_bail_out("I can't execute that command")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_case_insensitive(self) -> None:
        """Pattern matching should be case-insensitive."""
        result = detect_bail_out("I CAN'T EXECUTE THAT COMMAND")
        assert result is not None

    def test_all_six_patterns(self) -> None:
        """All 6 BAIL_OUT_PATTERNS should detect correctly."""
        assert len(BAIL_OUT_PATTERNS) == 6
        canonical_cases = [
            "I can't do this",  # cannot_execute
            "I'm unable to perform this action",  # unable_to
            "I don't have the ability to help",  # no_ability
            "Let me know if you'd like me to proceed",  # suggest_instead
            "Would you like me to do that?",  # would_you_like
            "I cannot directly access that file",  # cannot_directly
        ]
        for text in canonical_cases:
            result = detect_bail_out(text)
            assert result is not None, f"Expected bail-out detection for: {text!r}"


# ---------------------------------------------------------------------------
# make_follow_through_hook — hook factory tests
# ---------------------------------------------------------------------------


class TestMakeFollowThroughHook:
    """Tests for the hook factory and the returned async hook."""

    def test_hook_is_callable(self) -> None:
        """make_follow_through_hook() should return a callable."""
        hook = make_follow_through_hook()
        assert callable(hook)

    async def test_hook_signals_retry_on_bail_out(self) -> None:
        """Hook should set data['retry_needed'] = True when bail-out is detected."""
        hook = make_follow_through_hook(max_retries=2)
        data: dict = {
            "response_text": "I can't execute that command",
            "turn_id": "turn-1",
        }
        result = await hook(HookEvent.POST_LLM_CALL, data)
        assert result is not None
        assert result["retry_needed"] is True

    async def test_hook_adds_retry_prompt(self) -> None:
        """Hook should include 'retry_prompt' in returned data on bail-out."""
        hook = make_follow_through_hook(max_retries=2)
        data: dict = {
            "response_text": "I'm unable to perform this action",
            "turn_id": "turn-2",
        }
        result = await hook(HookEvent.POST_LLM_CALL, data)
        assert result is not None
        assert "retry_prompt" in result
        assert isinstance(result["retry_prompt"], str)
        assert len(result["retry_prompt"]) > 0

    async def test_hook_no_modification_on_clean_response(self) -> None:
        """Hook should return None when no bail-out is detected."""
        hook = make_follow_through_hook()
        data: dict = {
            "response_text": "Here is the output of ls -la",
            "turn_id": "turn-3",
        }
        result = await hook(HookEvent.POST_LLM_CALL, data)
        assert result is None

    async def test_max_retries_respected(self) -> None:
        """After max_retries, hook should return None (let response through)."""
        hook = make_follow_through_hook(max_retries=2)
        bail_out_data = lambda turn_id: {  # noqa: E731
            "response_text": "I can't execute that command",
            "turn_id": turn_id,
        }
        # First two retries should signal retry
        result1 = await hook(HookEvent.POST_LLM_CALL, bail_out_data("turn-max"))
        assert result1 is not None and result1["retry_needed"] is True

        result2 = await hook(HookEvent.POST_LLM_CALL, bail_out_data("turn-max"))
        assert result2 is not None and result2["retry_needed"] is True

        # Third attempt exceeds max_retries=2 → should let through (return None)
        result3 = await hook(HookEvent.POST_LLM_CALL, bail_out_data("turn-max"))
        assert result3 is None

    async def test_hook_ignores_non_post_llm_call_events(self) -> None:
        """Hook should return None for events other than POST_LLM_CALL."""
        hook = make_follow_through_hook()
        data: dict = {"response_text": "I can't execute that", "turn_id": "turn-x"}
        result = await hook(HookEvent.PRE_LLM_CALL, data)
        assert result is None

    async def test_hook_with_content_key(self) -> None:
        """Hook should also check 'content' key if 'response_text' is absent."""
        hook = make_follow_through_hook()
        data: dict = {
            "content": "I'm unable to do this",
            "turn_id": "turn-content",
        }
        result = await hook(HookEvent.POST_LLM_CALL, data)
        assert result is not None
        assert result["retry_needed"] is True

    async def test_hook_no_modification_on_empty_response(self) -> None:
        """Hook should return None when response_text is empty."""
        hook = make_follow_through_hook()
        data: dict = {"response_text": "", "turn_id": "turn-empty"}
        result = await hook(HookEvent.POST_LLM_CALL, data)
        assert result is None

    async def test_custom_retry_prompt(self) -> None:
        """Custom retry_prompt should be reflected in returned data."""
        custom_prompt = "Do it now, no excuses."
        hook = make_follow_through_hook(retry_prompt=custom_prompt)
        data: dict = {
            "response_text": "I cannot directly access that",
            "turn_id": "turn-custom",
        }
        result = await hook(HookEvent.POST_LLM_CALL, data)
        assert result is not None
        assert result["retry_prompt"] == custom_prompt

    async def test_retry_count_resets_after_max(self) -> None:
        """After max_retries is hit, subsequent turns start fresh."""
        hook = make_follow_through_hook(max_retries=1)
        data = lambda turn_id: {  # noqa: E731
            "response_text": "I can't execute that",
            "turn_id": turn_id,
        }
        # Exhaust retries for turn-A
        await hook(HookEvent.POST_LLM_CALL, data("turn-A"))  # count=1
        result_exceed = await hook(HookEvent.POST_LLM_CALL, data("turn-A"))  # exceeds max
        assert result_exceed is None  # let through + reset

        # A fresh call for turn-A should start fresh (reset happened)
        result_fresh = await hook(HookEvent.POST_LLM_CALL, data("turn-A"))
        assert result_fresh is not None
        assert result_fresh["retry_needed"] is True

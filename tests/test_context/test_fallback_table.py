"""Tests for context window fallback table."""

from __future__ import annotations


from sage.context.fallback_table import CONTEXT_WINDOW_TABLE, PATTERN_TABLE, get_context_window


class TestContextWindowTableContents:
    def test_table_is_dict(self) -> None:
        assert isinstance(CONTEXT_WINDOW_TABLE, dict)

    def test_pattern_table_is_list(self) -> None:
        assert isinstance(PATTERN_TABLE, list)

    def test_known_models_present(self) -> None:
        expected_models = [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4",
            "gpt-3.5-turbo",
            "claude-3-5-sonnet-20241022",
            "claude-3-haiku-20240307",
            "claude-3-opus-20240229",
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "llama3",
            "llama3.1",
            "mistral",
            "gemini-pro",
            "gemini-1.5-pro",
        ]
        for model in expected_models:
            assert model in CONTEXT_WINDOW_TABLE, f"Missing model: {model}"

    def test_all_values_are_positive_ints(self) -> None:
        for model, size in CONTEXT_WINDOW_TABLE.items():
            assert isinstance(size, int), f"{model}: expected int, got {type(size)}"
            assert size > 0, f"{model}: context window must be positive"


class TestGetContextWindowExactMatch:
    def test_gpt4o_exact(self) -> None:
        assert get_context_window("gpt-4o") == 128000

    def test_gpt4o_mini_exact(self) -> None:
        assert get_context_window("gpt-4o-mini") == 128000

    def test_gpt4_exact(self) -> None:
        assert get_context_window("gpt-4") == 8192

    def test_gpt35_turbo_exact(self) -> None:
        assert get_context_window("gpt-3.5-turbo") == 16385

    def test_claude_35_sonnet_exact(self) -> None:
        assert get_context_window("claude-3-5-sonnet-20241022") == 200000

    def test_claude_haiku_exact(self) -> None:
        assert get_context_window("claude-3-haiku-20240307") == 200000

    def test_claude_opus_exact(self) -> None:
        assert get_context_window("claude-3-opus-20240229") == 200000

    def test_claude_opus_46_exact(self) -> None:
        assert get_context_window("claude-opus-4-6") == 200000

    def test_claude_sonnet_46_exact(self) -> None:
        assert get_context_window("claude-sonnet-4-6") == 200000

    def test_llama3_exact(self) -> None:
        assert get_context_window("llama3") == 8192

    def test_llama31_exact(self) -> None:
        assert get_context_window("llama3.1") == 128000

    def test_mistral_exact(self) -> None:
        assert get_context_window("mistral") == 32768

    def test_gemini_pro_exact(self) -> None:
        assert get_context_window("gemini-pro") == 32768

    def test_gemini_15_pro_exact(self) -> None:
        assert get_context_window("gemini-1.5-pro") == 1000000


class TestGetContextWindowPatternMatch:
    def test_gpt4o_versioned_pattern(self) -> None:
        # gpt-4o* pattern -> 128000
        assert get_context_window("gpt-4o-2025-01-01") == 128000

    def test_gpt4o_turbo_pattern(self) -> None:
        assert get_context_window("gpt-4o-turbo") == 128000

    def test_gpt4_turbo_pattern(self) -> None:
        # gpt-4* pattern -> 8192 (matches gpt-4-turbo when no exact match)
        assert get_context_window("gpt-4-turbo-preview") == 8192

    def test_claude_3_pattern(self) -> None:
        # claude-3* -> 200000
        assert get_context_window("claude-3-new-model") == 200000

    def test_claude_opus_pattern(self) -> None:
        # claude-opus* -> 200000
        assert get_context_window("claude-opus-5-0") == 200000

    def test_claude_sonnet_pattern(self) -> None:
        # claude-sonnet* -> 200000
        assert get_context_window("claude-sonnet-5-0") == 200000

    def test_claude_haiku_pattern(self) -> None:
        # claude-haiku* -> 200000
        assert get_context_window("claude-haiku-5-0") == 200000

    def test_llama3_versioned_pattern(self) -> None:
        # llama3* -> 128000
        assert get_context_window("llama3.2") == 128000

    def test_gemini_15_pattern(self) -> None:
        # gemini-1.5* -> 1000000
        assert get_context_window("gemini-1.5-flash") == 1000000

    def test_gemini_pattern_fallback(self) -> None:
        # gemini* -> 32768 (non-1.5 gemini)
        assert get_context_window("gemini-ultra") == 32768

    def test_pattern_first_match_wins(self) -> None:
        # gpt-4o* comes before gpt-4* in PATTERN_TABLE, so gpt-4o-X -> 128000 not 8192
        result = get_context_window("gpt-4o-anything")
        assert result == 128000


class TestGetContextWindowDefault:
    def test_unknown_model_returns_default(self) -> None:
        assert get_context_window("totally-unknown") == 4096

    def test_unknown_model_custom_default(self) -> None:
        assert get_context_window("unknown", default=8192) == 8192

    def test_empty_string_returns_default(self) -> None:
        assert get_context_window("", default=4096) == 4096

    def test_default_is_4096_when_not_specified(self) -> None:
        result = get_context_window("not-a-real-model-xyz-abc")
        assert result == 4096


class TestGetContextWindowNoDependencies:
    def test_no_litellm_import_in_fallback_table(self) -> None:
        """Ensure fallback_table.py has no litellm dependency."""
        import sys

        # Remove litellm from sys.modules temporarily to verify fallback_table
        # can be imported without it
        litellm_modules = {k: v for k, v in sys.modules.items() if "litellm" in k}
        for k in litellm_modules:
            del sys.modules[k]

        # Re-import the module — should succeed without litellm
        if "sage.context.fallback_table" in sys.modules:
            del sys.modules["sage.context.fallback_table"]

        try:
            import sage.context.fallback_table as ft

            assert hasattr(ft, "get_context_window")
        finally:
            # Restore litellm modules
            sys.modules.update(litellm_modules)

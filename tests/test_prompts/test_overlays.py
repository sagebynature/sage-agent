from __future__ import annotations

import pytest

from sage.prompts.overlays import GeminiOverlay, GPTOverlay, OverlayRegistry, PromptOverlay


class TestGeminiOverlay:
    def test_applies_to_gemini_prefix(self) -> None:
        overlay = GeminiOverlay()
        assert overlay.applies_to("gemini/gemini-2.0-flash") is True
        assert overlay.applies_to("gemini/gemini-1.5-pro") is True

    def test_does_not_apply_to_other_models(self) -> None:
        overlay = GeminiOverlay()
        assert overlay.applies_to("gpt-4o") is False
        assert overlay.applies_to("anthropic/claude-3-5-sonnet") is False
        assert overlay.applies_to("ollama/llama3") is False

    def test_transform_appends_reminder(self) -> None:
        overlay = GeminiOverlay()
        result = overlay.transform("You are a helper.")
        assert "ALWAYS use tools" in result
        assert result.startswith("You are a helper.")

    def test_transform_idempotent_base(self) -> None:
        overlay = GeminiOverlay()
        once = overlay.transform("base")
        twice = overlay.transform("base")
        assert once == twice


class TestGPTOverlay:
    def test_applies_to_gpt_prefix(self) -> None:
        overlay = GPTOverlay()
        assert overlay.applies_to("gpt-4o") is True
        assert overlay.applies_to("gpt-3.5-turbo") is True
        assert overlay.applies_to("gpt-4o-mini") is True

    def test_does_not_apply_to_other_models(self) -> None:
        overlay = GPTOverlay()
        assert overlay.applies_to("gemini/gemini-2.0-flash") is False
        assert overlay.applies_to("anthropic/claude-3-5-sonnet") is False

    def test_transform_appends_step_hint(self) -> None:
        overlay = GPTOverlay()
        result = overlay.transform("You are a helper.")
        assert "clear steps" in result
        assert result.startswith("You are a helper.")


class TestOverlayRegistry:
    def test_gemini_model_receives_overlay(self) -> None:
        reg = OverlayRegistry()
        result = reg.apply("gemini/gemini-2.0-flash", "base prompt")
        assert "ALWAYS use tools" in result

    def test_gpt_model_receives_overlay(self) -> None:
        reg = OverlayRegistry()
        result = reg.apply("gpt-4o", "base prompt")
        assert "clear steps" in result

    def test_unknown_model_unchanged(self) -> None:
        reg = OverlayRegistry()
        result = reg.apply("anthropic/claude-3-5-sonnet", "base prompt")
        assert result == "base prompt"

    def test_register_custom_overlay(self) -> None:
        class MyOverlay:
            def applies_to(self, model: str) -> bool:
                return model == "my-model"

            def transform(self, prompt: str) -> str:
                return prompt + " [MY]"

        reg = OverlayRegistry()
        reg.register(MyOverlay())
        assert reg.apply("my-model", "x") == "x [MY]"
        assert reg.apply("gpt-4o", "x") == "x\n\nFormat your reasoning in clear steps."

    def test_empty_prompt_still_applies_overlay(self) -> None:
        reg = OverlayRegistry()
        result = reg.apply("gemini/gemini-2.0-flash", "")
        assert "ALWAYS use tools" in result

    def test_protocol_compliance(self) -> None:
        assert isinstance(GeminiOverlay(), PromptOverlay)
        assert isinstance(GPTOverlay(), PromptOverlay)


class TestAgentSystemMessageOverlay:
    """Integration: agent._build_system_message applies overlays based on model."""

    @pytest.mark.asyncio
    async def test_gemini_agent_gets_overlay_in_system_message(self) -> None:
        from sage.agent import Agent
        from sage.models import CompletionResult, Message, Usage

        class MockProvider:
            async def complete(self, messages, tools=None, **kwargs):
                return CompletionResult(
                    message=Message(role="assistant", content="done"),
                    usage=Usage(),
                )

        agent = Agent(
            name="t",
            model="gemini/gemini-2.0-flash",
            body="You are a helper.",
            provider=MockProvider(),
        )
        system_msg = agent._build_system_message()
        assert "ALWAYS use tools" in system_msg

    @pytest.mark.asyncio
    async def test_gpt_agent_gets_overlay_in_system_message(self) -> None:
        from sage.agent import Agent
        from sage.models import CompletionResult, Message, Usage

        class MockProvider:
            async def complete(self, messages, tools=None, **kwargs):
                return CompletionResult(
                    message=Message(role="assistant", content="done"),
                    usage=Usage(),
                )

        agent = Agent(
            name="t",
            model="gpt-4o",
            body="You are a helper.",
            provider=MockProvider(),
        )
        system_msg = agent._build_system_message()
        assert "clear steps" in system_msg

    @pytest.mark.asyncio
    async def test_other_model_no_overlay(self) -> None:
        from sage.agent import Agent
        from sage.models import CompletionResult, Message, Usage

        class MockProvider:
            async def complete(self, messages, tools=None, **kwargs):
                return CompletionResult(
                    message=Message(role="assistant", content="done"),
                    usage=Usage(),
                )

        agent = Agent(
            name="t",
            model="anthropic/claude-3-5-sonnet",
            body="You are a helper.",
            provider=MockProvider(),
        )
        system_msg = agent._build_system_message()
        assert system_msg == "You are a helper."

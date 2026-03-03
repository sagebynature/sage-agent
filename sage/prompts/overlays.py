"""Model-specific prompt overlays.

Overlays are lightweight transformations applied to the assembled system
prompt *after* all other content (body, identity, skills catalog) has been
joined.  Each overlay targets a family of models via ``applies_to`` and
appends or prepends model-specific instructions.

Usage::

    from sage.prompts.overlays import registry as overlay_registry

    final_prompt = overlay_registry.apply(model, base_prompt)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PromptOverlay(Protocol):
    """Protocol for a single prompt overlay.

    An overlay must implement two methods:

    * ``applies_to(model)`` — return ``True`` when this overlay is relevant
      for the given *model* string.
    * ``transform(prompt)`` — return the (possibly extended) prompt string.
    """

    def applies_to(self, model: str) -> bool: ...

    def transform(self, prompt: str) -> str: ...


class GeminiOverlay:
    """Aggressive tool-call enforcement reminder for Gemini models.

    Gemini models occasionally skip available tools.  This overlay appends
    a short reminder to always prefer tool calls over bare text responses.
    """

    def applies_to(self, model: str) -> bool:
        return model.startswith("gemini/")

    def transform(self, prompt: str) -> str:
        reminder = "\n\nIMPORTANT: ALWAYS use tools if available. Do not skip tool calls."
        return prompt + reminder


class GPTOverlay:
    """Structured reasoning hint for GPT models.

    GPT models benefit from explicit instruction to format their reasoning
    in clear steps, which improves consistency of multi-step outputs.
    """

    def applies_to(self, model: str) -> bool:
        return model.startswith("gpt-")

    def transform(self, prompt: str) -> str:
        return prompt + "\n\nFormat your reasoning in clear steps."


class OverlayRegistry:
    """Registry of :class:`PromptOverlay` instances.

    Applies every registered overlay whose ``applies_to`` returns ``True``
    for the given model.  Overlays are applied in insertion order.

    Example::

        registry = OverlayRegistry()
        final = registry.apply("gemini/gemini-2.0-flash", "You are a helper.")
        # → "You are a helper.\\n\\nIMPORTANT: ALWAYS use tools …"
    """

    def __init__(self) -> None:
        self._overlays: list[PromptOverlay] = [GeminiOverlay(), GPTOverlay()]

    def register(self, overlay: PromptOverlay) -> None:
        """Add a custom overlay to the end of the chain."""
        self._overlays.append(overlay)

    def apply(self, model: str, prompt: str) -> str:
        """Apply all matching overlays to *prompt* and return the result."""
        for overlay in self._overlays:
            if overlay.applies_to(model):
                prompt = overlay.transform(prompt)
        return prompt


#: Module-level singleton registry — used by Agent._build_system_message.
registry = OverlayRegistry()

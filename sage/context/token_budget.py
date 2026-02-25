"""Token-aware context budget management."""

from __future__ import annotations

import logging
from typing import Any

import litellm

from sage.models import Message

logger = logging.getLogger(__name__)


class TokenBudget:
    """Tracks token usage against a model's context window.

    Uses ``litellm.token_counter()`` for model-specific counting
    and ``litellm.get_max_tokens()`` for context window limits.
    """

    def __init__(
        self,
        model: str,
        compaction_threshold: float = 0.75,
        reserve_tokens: int = 4096,
    ) -> None:
        self.model = model
        max_tokens = litellm.get_max_tokens(model)
        if not max_tokens:
            raise ValueError(
                f"Cannot determine max_tokens for model '{model}'. "
                "Ensure the model is supported by litellm."
            )
        self.max_tokens: int = int(max_tokens)
        self.compaction_threshold = compaction_threshold
        self.reserve_tokens = reserve_tokens

    @property
    def available_tokens(self) -> int:
        """Tokens available for conversation (max minus reserve)."""
        return self.max_tokens - self.reserve_tokens

    def count_messages(self, messages: list[Message]) -> int:
        """Count tokens in a message list using litellm's model-specific tokenizer."""
        msg_dicts = []
        for m in messages:
            d: dict[str, Any] = {"role": m.role}
            if m.content is not None:
                d["content"] = m.content
            msg_dicts.append(d)

        return int(litellm.token_counter(model=self.model, messages=msg_dicts))

    def should_compact(self, messages: list[Message]) -> bool:
        """Return True if current messages exceed the compaction threshold."""
        used = self.count_messages(messages)
        limit = int(self.available_tokens * self.compaction_threshold)
        return used >= limit

    def usage_report(self, messages: list[Message]) -> dict[str, Any]:
        """Return usage statistics for observability."""
        used = self.count_messages(messages)
        available = self.available_tokens
        pct = round(used / available * 100, 1) if available > 0 else 0.0
        return {
            "tokens_used": used,
            "tokens_available": available,
            "utilization_pct": pct,
            "should_compact": used >= int(available * self.compaction_threshold),
        }

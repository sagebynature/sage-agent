"""Action follow-through guardrail — detect and retry LLM bail-outs."""

import re
import logging
from collections.abc import Callable
from typing import Any
from sage.hooks.base import HookEvent

logger = logging.getLogger(__name__)

# Compiled patterns for bail-out language
BAIL_OUT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("cannot_execute", re.compile(r"(?i)I (can'?t|cannot) (do|perform|execute|complete)")),
    ("unable_to", re.compile(r"(?i)I'?m (unable|not able) to")),
    ("no_ability", re.compile(r"(?i)I don'?t have (the ability|access|permission)")),
    ("suggest_instead", re.compile(r"(?i)Let me know if you'?d like me to")),
    ("would_you_like", re.compile(r"(?i)Would you like me to")),
    ("cannot_directly", re.compile(r"(?i)I cannot directly")),
]


def detect_bail_out(text: str) -> str | None:
    """Detect if text contains bail-out language.

    Returns the pattern name (description) if detected, None otherwise.
    """
    for name, pattern in BAIL_OUT_PATTERNS:
        if pattern.search(text):
            return name
    return None


def make_follow_through_hook(
    *,
    max_retries: int = 2,
    retry_prompt: str = "Please proceed with the action instead of describing what you would do.",
) -> Callable[..., Any]:
    """Factory returning a post_llm_call hook for detecting bail-outs.

    Hook behavior: if bail-out detected in assistant response, signal retry needed.
    Tracks retry count in data dict. After max_retries, logs warning and lets through.

    This is a MODIFYING hook (returns dict or None).
    Returns modified data with 'retry_needed': True and 'retry_prompt' when bail-out detected.
    Returns None (no modification) when no bail-out or max retries exceeded.
    """
    retry_counts: dict[str, int] = {}  # keyed by some turn identifier

    async def _hook(event: HookEvent, data: dict[str, Any]) -> dict[str, Any] | None:
        if event != HookEvent.POST_LLM_CALL:
            return None

        response_text = data.get("response_text", "") or data.get("content", "") or ""
        if not response_text:
            return None

        bail_out = detect_bail_out(response_text)
        if not bail_out:
            return None

        # Use a turn_id from data, or generate one
        turn_id = str(data.get("turn_id", "default"))
        current_count = retry_counts.get(turn_id, 0)

        if current_count >= max_retries:
            logger.warning(
                "Bail-out detected (%s) but max_retries=%d exceeded. Letting response through.",
                bail_out,
                max_retries,
            )
            retry_counts.pop(turn_id, None)  # reset for next turn
            return None

        retry_counts[turn_id] = current_count + 1
        logger.info(
            "Bail-out detected (%s), retry %d/%d",
            bail_out,
            current_count + 1,
            max_retries,
        )
        data["retry_needed"] = True
        data["retry_prompt"] = retry_prompt
        return data

    return _hook

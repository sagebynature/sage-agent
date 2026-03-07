"""Credential scrubbing hook — removes secrets from tool output via regex."""

from __future__ import annotations

import logging
import re
from typing import Any

from sage.hooks.base import HookEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled regex patterns for common secrets (pre-compiled at module load
# for performance — avoids per-call recompilation overhead).
# ---------------------------------------------------------------------------
PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[a-zA-Z0-9\-]{20,}"),  # OpenAI-style API keys (incl. sk-proj-...)
    re.compile(r"key-[a-zA-Z0-9]{20,}"),  # Generic key- prefixed keys
    re.compile(r"Bearer [a-zA-Z0-9\-._~+\/]+=*"),  # Bearer tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access keys
    re.compile(r"(?i)(password|secret|token|api_key)\s*[=:]\s*\S+"),  # Generic key=value secrets
]

# ---------------------------------------------------------------------------
# Allowlist patterns — matches that overlap with these are NOT scrubbed.
# ---------------------------------------------------------------------------
ALLOWLIST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        re.IGNORECASE,
    ),  # UUIDs (8-4-4-4-12)
    re.compile(r"\b[0-9a-f]{40}\b", re.IGNORECASE),  # SHA-1 hashes (git commits)
    re.compile(r"\b[0-9a-f]{64}\b", re.IGNORECASE),  # SHA-256 hashes
]


def _is_allowlisted(matched_text: str) -> bool:
    """Return True if *matched_text* overlaps with an allowlisted pattern.

    Args:
        matched_text: The substring captured by a secret-detection pattern.

    Returns:
        ``True`` if the text should be preserved (not scrubbed).
    """
    for allow_pat in ALLOWLIST_PATTERNS:
        if allow_pat.search(matched_text):
            return True
    return False


def scrub_text(text: str, *, preserve_prefix: int = 4) -> str:
    """Replace credential patterns with ``{prefix}***REDACTED***``.

    Args:
        text: Input text to scrub.
        preserve_prefix: Number of leading characters of each match to
            preserve in the output.  Defaults to ``4``.

    Returns:
        A copy of *text* with detected secrets replaced.  If no secrets are
        found the original string is returned unchanged.
    """
    result = text
    for pattern in PATTERNS:

        def _replacer(match: re.Match[str], pp: int = preserve_prefix) -> str:
            matched = match.group(0)
            if _is_allowlisted(matched):
                return matched
            if pp > 0 and len(matched) > pp:
                prefix = matched[:pp]
            elif pp == 0:
                prefix = ""
            else:
                # preserve_prefix >= len(matched) — keep whole match as prefix
                prefix = matched
            return f"{prefix}***REDACTED***"

        result = pattern.sub(_replacer, result)
    return result


def make_credential_scrubber() -> Any:
    """Factory returning a post_tool_execute hook that scrubs credentials from output.

    The returned hook is an async callable matching the :class:`~sage.hooks.base.HookHandler`
    protocol.  It operates as a *void* hook — it modifies ``data["output"]`` in
    place and returns ``None``.

    Returns:
        An async hook function suitable for registration with a hook registry.
    """

    async def _hook(event: HookEvent, data: dict[str, Any]) -> None:
        """Scrub credentials from tool output (void hook — side-effect only)."""
        if event != HookEvent.POST_TOOL_EXECUTE:
            return
        target_key = "result" if isinstance(data.get("result"), str) else "output"
        if target_key in data and isinstance(data[target_key], str):
            original = data[target_key]
            scrubbed = scrub_text(original)
            if scrubbed != original:
                logger.warning("Credentials detected and scrubbed from tool output")
                data[target_key] = scrubbed

    return _hook

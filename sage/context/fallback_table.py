"""Static context window size lookup table — no network calls, no litellm dependency."""

from __future__ import annotations

import fnmatch

CONTEXT_WINDOW_TABLE: dict[str, int] = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-haiku-20240307": 200000,
    "claude-3-opus-20240229": 200000,
    "claude-opus-4-6": 200000,
    "claude-sonnet-4-6": 200000,
    "claude-haiku-4-5-20251001": 200000,
    "llama3": 8192,
    "llama3.1": 128000,
    "mistral": 32768,
    "gemini-pro": 32768,
    "gemini-1.5-pro": 1000000,
}

PATTERN_TABLE: list[tuple[str, int]] = [
    ("gpt-4o*", 128000),
    ("gpt-4*", 8192),
    ("claude-3*", 200000),
    ("claude-opus*", 200000),
    ("claude-sonnet*", 200000),
    ("claude-haiku*", 200000),
    ("llama3*", 128000),
    ("gemini-1.5*", 1000000),
    ("gemini*", 32768),
]


def get_context_window(model: str, default: int = 4096) -> int:
    """Lookup context window size for a model. No network calls.

    Lookup order:
    1. Exact match in CONTEXT_WINDOW_TABLE
    2. Pattern match via PATTERN_TABLE (first match wins, uses fnmatch)
    3. Return default
    """
    # 1. Exact match
    if model in CONTEXT_WINDOW_TABLE:
        return CONTEXT_WINDOW_TABLE[model]

    # 2. Pattern match (first match wins)
    for pattern, size in PATTERN_TABLE:
        if fnmatch.fnmatch(model, pattern):
            return size

    # 3. Default
    return default

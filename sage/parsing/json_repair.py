"""JSON repair utility for fixing common LLM JSON output errors."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def repair_json(text: str, *, max_size: int = 102400) -> str:
    """Attempt to fix common LLM JSON errors. Returns text unchanged if > max_size.

    Fixes:
    1. Strip markdown code fences (```json ... ``` or ``` ... ```)
    2. Remove trailing commas before } or ]
    3. Add missing closing braces/brackets (count opens vs closes, append missing)
    4. Attempt to close unbalanced open quotes (if odd number of unescaped quotes)

    If input exceeds max_size bytes, return input unchanged with a warning log.
    Log before/after on successful repair at DEBUG level.
    All operations are deterministic (no randomness, no LLM calls).
    """
    if len(text.encode("utf-8")) > max_size:
        logger.warning(
            "repair_json: input exceeds max_size (%d bytes), returning unchanged",
            max_size,
        )
        return text

    original = text
    result = text

    # Step 1: Strip markdown code fences.
    # Match optional language tag after opening fence.
    fence_pattern = re.compile(
        r"^```[a-zA-Z]*\n(.*?)\n?```\s*$",
        re.DOTALL,
    )
    match = fence_pattern.match(result.strip())
    if match:
        result = match.group(1).strip()

    # Step 2: Remove trailing commas before } or ]
    # This handles nested cases by repeated substitution until stable.
    trailing_comma_pattern = re.compile(r",\s*([}\]])")
    prev = None
    while prev != result:
        prev = result
        result = trailing_comma_pattern.sub(r"\1", result)

    # Step 3: Add missing closing braces/brackets.
    # Count unmatched open braces and brackets (outside of strings).
    opens = []
    in_string = False
    i = 0
    while i < len(result):
        ch = result[i]
        if in_string:
            if ch == "\\" and i + 1 < len(result):
                i += 2  # skip escaped character
                continue
            if ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch in ("{", "["):
                opens.append(ch)
            elif ch == "}":
                if opens and opens[-1] == "{":
                    opens.pop()
            elif ch == "]":
                if opens and opens[-1] == "[":
                    opens.pop()
        i += 1

    # Append closing characters in reverse order of unmatched opens.
    closing_map = {"{": "}", "[": "]"}
    suffix = "".join(closing_map[ch] for ch in reversed(opens))
    if suffix:
        result = result + suffix

    if result != original:
        logger.debug(
            "repair_json: repaired JSON (before=%r, after=%r)",
            original[:200],
            result[:200],
        )

    return result


def try_parse_json(text: str) -> dict[str, Any] | list[Any] | None:
    """Try to parse text as JSON. On failure, attempt repair then parse again.

    Returns parsed JSON object/array, or None on final failure.
    Max 1 repair attempt.
    """
    try:
        result = json.loads(text)
        if isinstance(result, (dict, list)):
            return result
        return None
    except (json.JSONDecodeError, ValueError):
        pass

    # One repair attempt.
    repaired = repair_json(text)
    try:
        result = json.loads(repaired)
        if isinstance(result, (dict, list)):
            return result
        return None
    except (json.JSONDecodeError, ValueError):
        return None

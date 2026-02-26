"""Parse YAML frontmatter from markdown text."""

from __future__ import annotations

from typing import Any

import logging


logger = logging.getLogger(__name__)


def _coerce_permission_bools(meta: dict[str, Any]) -> dict[str, Any]:
    """Coerce YAML booleans in 'permission' block to 'allow'/'deny' strings.

    YAML boolean values (True/False from yes/no/true/false syntax) are converted:
    - True -> "allow"
    - False -> "deny"

    This only applies to the 'permission' key and its nested dicts.
    Booleans in other keys are left unchanged.
    Emits a logging.warning() when coercion occurs.

    Args:
        meta: Metadata dict from yaml.safe_load()

    Returns:
        Modified meta dict with permission booleans coerced to strings
    """
    if "permission" not in meta or not isinstance(meta["permission"], dict):
        return meta

    def _coerce_value(val: Any) -> Any:
        """Recursively coerce bool values to strings, or recurse on dicts."""
        if isinstance(val, bool):  # Check bool BEFORE int (bool is subclass of int)
            coerced = "allow" if val else "deny"
            logger.warning(f"Coerced YAML boolean {val!r} to '{coerced}' in permission block")
            return coerced
        elif isinstance(val, dict):
            return {k: _coerce_value(v) for k, v in val.items()}
        else:
            return val

    # Coerce all values in the permission dict
    meta["permission"] = {k: _coerce_value(v) for k, v in meta["permission"].items()}
    return meta


def parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from raw text.

    Returns tuple of (metadata_dict, body_string). On any error, returns
    ({}, full_text_stripped).
    """
    import yaml

    lines = raw.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, raw.strip()

    # Find closing delimiter
    end_index = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = i
            break

    if end_index is None:
        return {}, raw.strip()

    # Extract YAML block and body
    frontmatter_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).strip()

    try:
        meta = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return {}, raw.strip()

    # Ensure meta is a dict
    if not isinstance(meta, dict):
        return {}, body

    # Coerce YAML booleans in permission block to allow/deny strings
    meta = _coerce_permission_bools(meta)

    return meta, body

"""Parse YAML frontmatter from markdown text."""

from __future__ import annotations

from typing import Any


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

    return meta, body

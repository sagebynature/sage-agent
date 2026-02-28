"""AIEOS v1.2 identity loader and system prompt formatter."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sage.identity.models import (
    AieosIdentity,
    Bio,
    Idiolect,
    Names,
    NeuralMatrix,
    SkillEntry,
    TextStyle,
)

logger = logging.getLogger(__name__)


def load_identity(file_path: str | Path) -> AieosIdentity:
    """Load an AIEOS v1.2 identity from a JSON file.

    Extracts only the sections relevant to system prompt injection:
    ``identity``, ``psychology``, ``linguistics``, and ``capabilities``.
    All other top-level sections are silently ignored.

    Args:
        file_path: Path to an ``.aieos.json`` file.

    Returns:
        A parsed :class:`AieosIdentity` instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    path = Path(file_path)
    raw = json.loads(path.read_text(encoding="utf-8"))

    return _parse_aieos(raw)


def _parse_aieos(data: dict[str, Any]) -> AieosIdentity:
    """Parse raw AIEOS JSON into an ``AieosIdentity`` model."""
    identity_sec = data.get("identity", {})
    psych_sec = data.get("psychology", {})
    ling_sec = data.get("linguistics", {})
    caps_sec = data.get("capabilities", {})

    names = Names(**(identity_sec.get("names", {})))
    bio = Bio(**(identity_sec.get("bio", {})))

    neural_matrix = NeuralMatrix(**(psych_sec.get("neural_matrix", {})))

    text_style = TextStyle(**(ling_sec.get("text_style", {})))
    idiolect = Idiolect(**(ling_sec.get("idiolect", {})))

    skills: list[SkillEntry] = []
    for entry in caps_sec.get("skills", []):
        skills.append(SkillEntry(**entry))

    return AieosIdentity(
        names=names,
        bio=bio,
        neural_matrix=neural_matrix,
        text_style=text_style,
        idiolect=idiolect,
        skills=skills,
    )


def format_identity_prompt(identity: AieosIdentity) -> str:
    """Format an ``AieosIdentity`` as a text block suitable for system prompt injection.

    The output is a human-readable summary of the persona's traits that
    can be prepended/appended to the LLM's system prompt.

    Returns:
        A multi-line string; empty string if the identity has no meaningful data.
    """
    sections: list[str] = []

    # ── Identity ──────────────────────────────────────────────────────
    name_parts = [
        p
        for p in [
            identity.names.first,
            identity.names.middle,
            identity.names.last,
        ]
        if p
    ]
    if name_parts:
        line = f"Name: {' '.join(name_parts)}"
        if identity.names.nickname:
            line += f' ("{identity.names.nickname}")'
        sections.append(line)

    bio_lines: list[str] = []
    if identity.bio.gender:
        bio_lines.append(f"Gender: {identity.bio.gender}")
    if identity.bio.age_perceived is not None:
        bio_lines.append(f"Perceived age: {identity.bio.age_perceived}")
    if bio_lines:
        sections.append("\n".join(bio_lines))

    # ── Psychology ────────────────────────────────────────────────────
    nm = identity.neural_matrix
    trait_lines = [
        f"  creativity={nm.creativity:.1f}",
        f"  empathy={nm.empathy:.1f}",
        f"  logic={nm.logic:.1f}",
        f"  adaptability={nm.adaptability:.1f}",
        f"  charisma={nm.charisma:.1f}",
        f"  reliability={nm.reliability:.1f}",
    ]
    sections.append("Personality traits:\n" + "\n".join(trait_lines))

    # ── Linguistics ───────────────────────────────────────────────────
    ts = identity.text_style
    style_lines = [
        f"Formality: {ts.formality_level:.1f}/1.0",
        f"Verbosity: {ts.verbosity_level:.1f}/1.0",
        f"Vocabulary: {ts.vocabulary_level}",
    ]
    if ts.slang_usage:
        style_lines.append("Uses slang: yes")
    if ts.style_descriptors:
        style_lines.append(f"Style: {', '.join(ts.style_descriptors)}")
    sections.append("Communication style:\n  " + "\n  ".join(style_lines))

    idi = identity.idiolect
    if idi.catchphrases:
        sections.append(f"Catchphrases: {', '.join(repr(c) for c in idi.catchphrases)}")
    if idi.forbidden_words:
        sections.append(f"Forbidden words: {', '.join(repr(w) for w in idi.forbidden_words)}")

    # ── Capabilities ──────────────────────────────────────────────────
    if identity.skills:
        skill_lines = [f"  - {s.name}: {s.description}" for s in identity.skills if s.name]
        if skill_lines:
            sections.append("Declared skills:\n" + "\n".join(skill_lines))

    if not sections:
        return ""

    return "## AIEOS Identity\n\n" + "\n\n".join(sections)

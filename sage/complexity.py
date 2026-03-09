"""Heuristic complexity scoring for effective LLM turns."""

from __future__ import annotations

from sage.config import ComplexityConfig
from sage.models import ComplexityFactor, ComplexityLevel, ComplexityScore, Message, ToolSchema


def _message_text(messages: list[Message]) -> str:
    return "".join(msg.content or "" for msg in messages if msg.content)


def _system_text(messages: list[Message]) -> str:
    return "".join(msg.content or "" for msg in messages if msg.role == "system" and msg.content)


def _derive_level(score: int, config: ComplexityConfig) -> ComplexityLevel:
    if score < config.simple_threshold:
        return "simple"
    if score < config.complex_threshold:
        return "medium"
    return "complex"


def score_turn_complexity(
    *,
    messages: list[Message],
    tool_schemas: list[ToolSchema] | None,
    config: ComplexityConfig,
) -> ComplexityScore:
    """Score a turn using OpenFang-inspired heuristics."""
    score = 0
    factors: list[ComplexityFactor] = []
    all_text = _message_text(messages)
    system_text = _system_text(messages)
    tool_count = len(tool_schemas or [])

    if config.features.message_length:
        contribution = len(all_text) // max(config.weights.message_chars_divisor, 1)
        if contribution > 0:
            factors.append(
                ComplexityFactor(
                    kind="message_length",
                    contribution=contribution,
                    value=len(all_text),
                )
            )
            score += contribution

    if config.features.tool_count:
        contribution = tool_count * config.weights.tool_count
        if contribution > 0:
            factors.append(
                ComplexityFactor(
                    kind="tool_count",
                    contribution=contribution,
                    value=tool_count,
                )
            )
            score += contribution

    if config.features.code_markers and config.code_markers:
        marker_matches = sum(1 for marker in config.code_markers if marker and marker in all_text)
        contribution = marker_matches * config.weights.code_marker
        if contribution > 0:
            factors.append(
                ComplexityFactor(
                    kind="code_markers",
                    contribution=contribution,
                    value=marker_matches,
                    details={"markers": list(config.code_markers)},
                )
            )
            score += contribution

    if config.features.conversation_depth:
        overage = max(0, len(messages) - config.history_baseline_messages)
        contribution = overage * config.weights.history_message_overage
        if contribution > 0:
            factors.append(
                ComplexityFactor(
                    kind="conversation_depth",
                    contribution=contribution,
                    value=overage,
                    details={"message_count": len(messages)},
                )
            )
            score += contribution

    if config.features.system_prompt_length:
        overage = max(0, len(system_text) - config.system_prompt_baseline_chars)
        contribution = overage // max(config.weights.system_prompt_overage_divisor, 1)
        if contribution > 0:
            factors.append(
                ComplexityFactor(
                    kind="system_prompt_length",
                    contribution=contribution,
                    value=overage,
                    details={"system_prompt_chars": len(system_text)},
                )
            )
            score += contribution

    return ComplexityScore(
        score=score,
        level=_derive_level(score, config),
        version=config.version,
        factors=factors,
        metadata={
            "message_count": len(messages),
            "message_chars": len(all_text),
            "system_prompt_chars": len(system_text),
            "tool_count": tool_count,
        },
    )

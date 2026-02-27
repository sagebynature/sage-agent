"""Rule-based query classifier for model routing."""

import re
import logging
from typing import Any
from pydantic import BaseModel
from sage.hooks.base import HookEvent

logger = logging.getLogger(__name__)


class ClassificationRule(BaseModel):
    """A single routing rule: match keywords/patterns, route to target_model."""

    keywords: list[str]  # case-insensitive substring matches
    patterns: list[str]  # regex patterns (compiled on use)
    priority: int  # higher = checked first
    target_model: str  # model to route to if this rule matches


class QueryClassifier:
    """Rule-based classifier that routes queries to different LLM models."""

    def __init__(self, rules: list[ClassificationRule]):
        self.rules = sorted(rules, key=lambda r: r.priority, reverse=True)  # highest first
        # Pre-compile patterns
        self._compiled: dict[int, list[re.Pattern]] = {
            id(rule): [re.compile(p, re.IGNORECASE) for p in rule.patterns] for rule in self.rules
        }

    def classify(self, query: str) -> str | None:
        """Return target_model of first matching rule, or None for no match.

        Matching: check keywords (case-insensitive substring), then patterns.
        First rule with ANY match wins (rules sorted by priority desc).
        """
        query_lower = query.lower()
        for rule in self.rules:
            # Check keywords
            for kw in rule.keywords:
                if kw.lower() in query_lower:
                    return rule.target_model
            # Check patterns
            for pat in self._compiled.get(id(rule), []):
                if pat.search(query):
                    return rule.target_model
        return None


def make_query_classifier(rules: list[ClassificationRule]):
    """Factory returning a pre_llm_call modifying hook for model routing."""
    classifier = QueryClassifier(rules=rules)

    async def _hook(event: HookEvent, data: dict[str, Any]) -> dict[str, Any] | None:
        """Route query to target model if a rule matches (modifying hook)."""
        if event != HookEvent.PRE_LLM_CALL:
            return None
        messages = data.get("messages", [])
        # Find the latest user message
        user_query = ""
        for msg in reversed(messages):
            role = getattr(msg, "role", None) or (
                msg.get("role") if isinstance(msg, dict) else None
            )
            if role == "user":
                content = getattr(msg, "content", None) or (
                    msg.get("content") if isinstance(msg, dict) else None
                )
                user_query = content or ""
                break
        if not user_query:
            return None
        target = classifier.classify(user_query)
        if target:
            old_model = data.get("model", "unknown")
            data["model"] = target
            logger.info(f"Query classifier routing from {old_model} to {target}")
            return data
        return None

    return _hook

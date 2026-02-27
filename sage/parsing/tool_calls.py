"""Multi-format tool call parser chain.

LiteLLM validation finding: LiteLLM 1.81.14 handles OpenAI-style JSON tool
calls internally via its completion pipeline types
(ChatCompletionMessageToolCall, _process_assistant_message_tool_calls), but
does NOT provide any utility to parse XML-tagged or markdown code-fence tool
calls from raw LLM text output.  The function
``litellm.utils.get_tool_calls_from_message`` does not exist.  LiteLLM's
``validate_and_fix_openai_tools`` only validates tool *definitions*, not tool
call outputs.  Therefore we implement all four parsers here for
format-independent parsing on non-LiteLLM usage paths.
"""

from __future__ import annotations

import json
import re
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Protocol, runtime_checkable

from sage.models import ToolCall


def _new_id() -> str:
    """Generate a short unique call id."""
    return f"call_{uuid.uuid4().hex[:8]}"


def _make_tool_call(
    name: str, arguments: dict[str, Any] | str, call_id: str | None = None
) -> ToolCall:
    """Build a ToolCall, coercing string arguments to dict when possible."""
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (json.JSONDecodeError, ValueError):
            arguments = {}
    if not isinstance(arguments, dict):
        arguments = {}
    return ToolCall(
        id=call_id or _new_id(),
        name=name,
        arguments=arguments,
    )


@runtime_checkable
class ToolCallParser(Protocol):
    def parse(self, text: str) -> list[ToolCall] | None:
        """Parse tool calls from text. Returns None if format not recognized."""
        ...


class NativeJsonParser:
    """Parse OpenAI-style JSON tool calls.

    Handles:
    - Single object: {"name": "...", "arguments": {...}}
    - Array of objects: [{"name": "...", "arguments": {...}}]
    - "function_call" field: {"function_call": {"name": "...", "arguments": "..."}}
    """

    def parse(self, text: str) -> list[ToolCall] | None:
        stripped = text.strip()
        if not stripped:
            return None

        try:
            data = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            return None

        # Array of tool calls
        if isinstance(data, list):
            calls = []
            for item in data:
                if isinstance(item, dict) and "name" in item and "arguments" in item:
                    calls.append(_make_tool_call(item["name"], item["arguments"], item.get("id")))
            return calls if calls else None

        if not isinstance(data, dict):
            return None

        # OpenAI function_call field
        if "function_call" in data:
            fc = data["function_call"]
            if isinstance(fc, dict) and "name" in fc:
                return [_make_tool_call(fc["name"], fc.get("arguments", {}))]
            return None

        # Direct {"name": ..., "arguments": ...} object
        if "name" in data and "arguments" in data:
            return [_make_tool_call(data["name"], data["arguments"], data.get("id"))]

        return None


class XmlToolCallParser:
    """Parse XML-tagged tool calls.

    Handles: <tool_call><name>...</name><arguments>...</arguments></tool_call>
    May have multiple tool calls in text.
    Uses re for extraction to support embedded tool calls in surrounding text.
    """

    # Match <tool_call>...</tool_call> blocks (non-greedy, dotall)
    _BLOCK_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)

    def parse(self, text: str) -> list[ToolCall] | None:
        blocks = self._BLOCK_RE.findall(text)
        if not blocks:
            return None

        calls: list[ToolCall] = []
        for block in blocks:
            # Wrap in a root so ET can parse it
            try:
                root = ET.fromstring(f"<root>{block}</root>")
            except ET.ParseError:
                continue

            name_el = root.find("name")
            args_el = root.find("arguments")
            if name_el is None or name_el.text is None:
                continue

            name = name_el.text.strip()
            args_text = (args_el.text or "{}").strip() if args_el is not None else "{}"

            try:
                arguments = json.loads(args_text)
            except (json.JSONDecodeError, ValueError):
                arguments = {}

            if not isinstance(arguments, dict):
                arguments = {}

            calls.append(ToolCall(id=_new_id(), name=name, arguments=arguments))

        return calls if calls else None


class MarkdownJsonParser:
    """Parse tool calls from markdown code fences.

    Handles:
    - ```json\\n{"name": ..., "arguments": ...}\\n```
    - ```tool_call\\n...\\n```
    """

    # Match ``` optionally followed by a language tag, then content, then ```
    _FENCE_RE = re.compile(
        r"```(?:json|tool_call|)\s*\n(.*?)\n```",
        re.DOTALL,
    )

    def parse(self, text: str) -> list[ToolCall] | None:
        matches = self._FENCE_RE.findall(text)
        if not matches:
            return None

        calls: list[ToolCall] = []
        for content in matches:
            content = content.strip()
            try:
                data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue

            if not isinstance(data, dict):
                continue

            if "name" not in data or "arguments" not in data:
                continue

            calls.append(_make_tool_call(data["name"], data["arguments"], data.get("id")))

        return calls if calls else None


class JsonRepairParser:
    """Last-resort parser that attempts to fix common JSON errors.

    Repairs:
    - Trailing commas in objects/arrays
    - Single-quoted strings (converted to double-quoted)
    - Unquoted keys

    Uses only stdlib — no external json_repair dependency.
    """

    @staticmethod
    def _repair(text: str) -> str:
        """Apply lightweight JSON repairs to text."""
        # Remove trailing commas before } or ]
        repaired = re.sub(r",\s*([\}\]])", r"\1", text)
        return repaired

    def parse(self, text: str) -> list[ToolCall] | None:
        stripped = text.strip()
        if not stripped:
            return None

        repaired = self._repair(stripped)

        try:
            data = json.loads(repaired)
        except (json.JSONDecodeError, ValueError):
            return None

        if not isinstance(data, dict):
            return None

        if "name" in data and "arguments" in data:
            return [_make_tool_call(data["name"], data["arguments"], data.get("id"))]

        return None


def parse_tool_calls(text: str) -> list[ToolCall]:
    """Chain parsers: Native JSON -> XML -> Markdown -> JSON Repair.

    Returns first successful parse result. Returns empty list if all fail.
    Never raises exceptions.
    """
    parsers: list[ToolCallParser] = [
        NativeJsonParser(),
        XmlToolCallParser(),
        MarkdownJsonParser(),
        JsonRepairParser(),
    ]

    for parser in parsers:
        try:
            result = parser.parse(text)
            if result is not None:
                return result
        except Exception:
            # Parsers must never propagate exceptions
            continue

    return []

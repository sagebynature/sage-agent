"""ToolDispatcher strategy pattern — selects between native and XML tool calling."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sage.models import ToolCall, ToolSchema


@runtime_checkable
class ToolDispatchStrategy(Protocol):
    def prepare_tools(self, schemas: list[ToolSchema]) -> dict[str, Any]:
        """Return kwargs to pass to the provider for tool calling.

        For native: returns {"tools": [...]} with OpenAI-format tool list.
        For XML: returns {"system_prompt_suffix": "..."} with XML tool descriptions.
        """
        ...

    def parse_response(self, response_text: str) -> list[ToolCall]:
        """Extract tool calls from a provider response.

        For native: response_text is unused (LiteLLM handles it).
        For XML: parse XML-formatted tool calls from response_text.
        Returns empty list if no tool calls found.
        """
        ...


class NativeToolDispatcher:
    """Uses provider's native function calling (OpenAI-style tools parameter).

    prepare_tools: converts ToolSchema list to OpenAI tools format.
    parse_response: returns [] (LiteLLM/provider already parsed tool_calls).
    """

    def prepare_tools(self, schemas: list[ToolSchema]) -> dict[str, Any]:
        """Return {"tools": [...]} with OpenAI-format tool dicts."""
        tools = []
        for schema in schemas:
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": schema.name,
                        "description": schema.description,
                        "parameters": schema.parameters,
                    },
                }
            )
        return {"tools": tools}

    def parse_response(self, response_text: str) -> list[ToolCall]:
        """Returns [] — native dispatchers rely on provider parsing."""
        return []


class XmlToolDispatcher:
    """Uses XML-formatted tool descriptions injected into system prompt.

    prepare_tools: serializes ToolSchemas as XML tool descriptions.
    parse_response: uses parse_tool_calls() to extract XML tool calls.
    """

    def prepare_tools(self, schemas: list[ToolSchema]) -> dict[str, Any]:
        """Return {"system_prompt_suffix": XML_description} for each tool."""
        lines = ["You have access to the following tools. Call them using XML format:\n"]
        for schema in schemas:
            lines.append("<tool>")
            lines.append(f"  <name>{schema.name}</name>")
            lines.append(f"  <description>{schema.description}</description>")
            lines.append("</tool>")
        lines.append(
            "\nTo call a tool, use: "
            "<tool_call><name>TOOL_NAME</name><arguments>{...}</arguments></tool_call>"
        )
        return {"system_prompt_suffix": "\n".join(lines)}

    def parse_response(self, response_text: str) -> list[ToolCall]:
        """Parse tool calls from XML-tagged response text."""
        from sage.parsing.tool_calls import parse_tool_calls

        return parse_tool_calls(response_text)


# Known non-function-calling model prefixes/patterns
_XML_DISPATCH_PREFIXES = ("ollama/", "ollama_chat/")
_XML_DISPATCH_MODELS: frozenset[str] = frozenset(
    {
        # Add known non-function-calling models here
    }
)


class AutoToolDispatcher:
    """Auto-selects dispatch strategy based on model name."""

    @staticmethod
    def for_model(model: str) -> ToolDispatchStrategy:
        """Return NativeToolDispatcher or XmlToolDispatcher based on model string.

        Heuristic:
        - ollama/* or ollama_chat/* → XmlToolDispatcher
        - known non-function-calling models → XmlToolDispatcher
        - everything else → NativeToolDispatcher
        """
        if any(model.startswith(prefix) for prefix in _XML_DISPATCH_PREFIXES):
            return XmlToolDispatcher()
        if model in _XML_DISPATCH_MODELS:
            return XmlToolDispatcher()
        return NativeToolDispatcher()

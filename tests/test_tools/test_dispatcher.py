"""Tests for ToolDispatcher strategy pattern."""

from __future__ import annotations


from sage.models import ToolCall, ToolSchema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_schema(name: str = "shell", description: str = "Run a command") -> ToolSchema:
    return ToolSchema(
        name=name,
        description=description,
        parameters={
            "type": "object",
            "properties": {"cmd": {"type": "string"}},
            "required": ["cmd"],
        },
    )


def _make_schemas(*names: str) -> list[ToolSchema]:
    return [_make_schema(name, f"Tool {name}") for name in names]


# ---------------------------------------------------------------------------
# NativeToolDispatcher tests
# ---------------------------------------------------------------------------


class TestNativeToolDispatcher:
    def test_native_prepare_tools_format(self):
        """Returns dict with 'tools' key containing correct structure."""
        from sage.tools.dispatcher import NativeToolDispatcher

        d = NativeToolDispatcher()
        schema = _make_schema("shell", "Run shell command")
        result = d.prepare_tools([schema])

        assert "tools" in result
        assert len(result["tools"]) == 1
        tool = result["tools"][0]
        assert tool["type"] == "function"
        assert "function" in tool
        assert tool["function"]["name"] == "shell"
        assert tool["function"]["description"] == "Run shell command"
        assert "parameters" in tool["function"]

    def test_native_prepare_multiple_tools(self):
        """3 schemas produce 3 tool entries in the list."""
        from sage.tools.dispatcher import NativeToolDispatcher

        d = NativeToolDispatcher()
        schemas = _make_schemas("shell", "file_read", "web_search")
        result = d.prepare_tools(schemas)

        assert "tools" in result
        assert len(result["tools"]) == 3
        names = [t["function"]["name"] for t in result["tools"]]
        assert names == ["shell", "file_read", "web_search"]

    def test_native_prepare_empty_schemas(self):
        """Empty schema list produces empty tools list."""
        from sage.tools.dispatcher import NativeToolDispatcher

        d = NativeToolDispatcher()
        result = d.prepare_tools([])
        assert result == {"tools": []}

    def test_native_parse_response_returns_empty(self):
        """parse_response always returns empty list (provider handles parsing)."""
        from sage.tools.dispatcher import NativeToolDispatcher

        d = NativeToolDispatcher()
        assert d.parse_response("") == []
        assert d.parse_response("some text") == []
        assert (
            d.parse_response(
                '<tool_call><name>shell</name><arguments>{"cmd":"ls"}</arguments></tool_call>'
            )
            == []
        )

    def test_native_parse_response_returns_list(self):
        """parse_response return type is always list."""
        from sage.tools.dispatcher import NativeToolDispatcher

        d = NativeToolDispatcher()
        result = d.parse_response("anything")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# XmlToolDispatcher tests
# ---------------------------------------------------------------------------


class TestXmlToolDispatcher:
    def test_xml_prepare_contains_system_suffix(self):
        """Returns dict with 'system_prompt_suffix' key."""
        from sage.tools.dispatcher import XmlToolDispatcher

        d = XmlToolDispatcher()
        result = d.prepare_tools([_make_schema()])
        assert "system_prompt_suffix" in result

    def test_xml_prepare_suffix_is_string(self):
        """system_prompt_suffix value is a non-empty string."""
        from sage.tools.dispatcher import XmlToolDispatcher

        d = XmlToolDispatcher()
        result = d.prepare_tools([_make_schema()])
        assert isinstance(result["system_prompt_suffix"], str)
        assert len(result["system_prompt_suffix"]) > 0

    def test_xml_prepare_contains_tool_names(self):
        """system_prompt_suffix contains each tool name."""
        from sage.tools.dispatcher import XmlToolDispatcher

        d = XmlToolDispatcher()
        schemas = _make_schemas("shell", "file_read", "web_search")
        result = d.prepare_tools(schemas)
        suffix = result["system_prompt_suffix"]

        for name in ["shell", "file_read", "web_search"]:
            assert name in suffix, f"Expected '{name}' in system_prompt_suffix"

    def test_xml_prepare_contains_descriptions(self):
        """system_prompt_suffix contains each tool description."""
        from sage.tools.dispatcher import XmlToolDispatcher

        d = XmlToolDispatcher()
        schema = _make_schema("shell", "Execute shell commands safely")
        result = d.prepare_tools([schema])
        suffix = result["system_prompt_suffix"]
        assert "Execute shell commands safely" in suffix

    def test_xml_prepare_multiple_tools(self):
        """All 3 tool names appear in the suffix."""
        from sage.tools.dispatcher import XmlToolDispatcher

        d = XmlToolDispatcher()
        schemas = _make_schemas("alpha", "beta", "gamma")
        result = d.prepare_tools(schemas)
        suffix = result["system_prompt_suffix"]
        assert "alpha" in suffix
        assert "beta" in suffix
        assert "gamma" in suffix

    def test_xml_parse_response_extracts_tool_calls(self):
        """parse_response extracts XML tool calls from response text."""
        from sage.tools.dispatcher import XmlToolDispatcher

        d = XmlToolDispatcher()
        response = 'I will run the shell. <tool_call><name>shell</name><arguments>{"cmd": "ls -la"}</arguments></tool_call>'
        result = d.parse_response(response)

        assert isinstance(result, list)
        assert len(result) == 1
        call = result[0]
        assert isinstance(call, ToolCall)
        assert call.name == "shell"
        assert call.arguments == {"cmd": "ls -la"}

    def test_xml_parse_response_no_tool_call(self):
        """parse_response returns empty list when no tool calls in text."""
        from sage.tools.dispatcher import XmlToolDispatcher

        d = XmlToolDispatcher()
        result = d.parse_response("This is a plain response with no tool calls.")
        assert result == []

    def test_xml_parse_response_multiple_calls(self):
        """parse_response extracts multiple tool calls from response text."""
        from sage.tools.dispatcher import XmlToolDispatcher

        d = XmlToolDispatcher()
        response = (
            '<tool_call><name>shell</name><arguments>{"cmd": "ls"}</arguments></tool_call>'
            " and "
            '<tool_call><name>file_read</name><arguments>{"path": "/etc/hosts"}</arguments></tool_call>'
        )
        result = d.parse_response(response)
        assert len(result) == 2
        assert result[0].name == "shell"
        assert result[1].name == "file_read"


# ---------------------------------------------------------------------------
# AutoToolDispatcher tests
# ---------------------------------------------------------------------------


class TestAutoToolDispatcher:
    def test_auto_ollama_returns_xml(self):
        """ollama/* model strings → XmlToolDispatcher."""
        from sage.tools.dispatcher import AutoToolDispatcher, XmlToolDispatcher

        d = AutoToolDispatcher.for_model("ollama/llama3")
        assert isinstance(d, XmlToolDispatcher)

    def test_auto_ollama_chat_returns_xml(self):
        """ollama_chat/* model strings → XmlToolDispatcher."""
        from sage.tools.dispatcher import AutoToolDispatcher, XmlToolDispatcher

        d = AutoToolDispatcher.for_model("ollama_chat/llama3")
        assert isinstance(d, XmlToolDispatcher)

    def test_auto_ollama_variant_returns_xml(self):
        """ollama/ with different model names → XmlToolDispatcher."""
        from sage.tools.dispatcher import AutoToolDispatcher, XmlToolDispatcher

        d = AutoToolDispatcher.for_model("ollama/mistral:7b")
        assert isinstance(d, XmlToolDispatcher)

    def test_auto_gpt4_returns_native(self):
        """gpt-4o → NativeToolDispatcher."""
        from sage.tools.dispatcher import AutoToolDispatcher, NativeToolDispatcher

        d = AutoToolDispatcher.for_model("gpt-4o")
        assert isinstance(d, NativeToolDispatcher)

    def test_auto_claude_returns_native(self):
        """anthropic/claude-* → NativeToolDispatcher."""
        from sage.tools.dispatcher import AutoToolDispatcher, NativeToolDispatcher

        d = AutoToolDispatcher.for_model("anthropic/claude-sonnet-4-20250514")
        assert isinstance(d, NativeToolDispatcher)

    def test_auto_gpt35_returns_native(self):
        """gpt-3.5-turbo → NativeToolDispatcher."""
        from sage.tools.dispatcher import AutoToolDispatcher, NativeToolDispatcher

        d = AutoToolDispatcher.for_model("gpt-3.5-turbo")
        assert isinstance(d, NativeToolDispatcher)

    def test_auto_unknown_model_returns_native(self):
        """Unknown model strings default to NativeToolDispatcher."""
        from sage.tools.dispatcher import AutoToolDispatcher, NativeToolDispatcher

        d = AutoToolDispatcher.for_model("some-unknown-provider/model-xyz")
        assert isinstance(d, NativeToolDispatcher)


# ---------------------------------------------------------------------------
# Protocol conformance tests
# ---------------------------------------------------------------------------


class TestStrategyProtocol:
    def test_strategy_protocol_native(self):
        """NativeToolDispatcher implements ToolDispatchStrategy protocol."""
        from sage.tools.dispatcher import NativeToolDispatcher, ToolDispatchStrategy

        d = NativeToolDispatcher()
        assert isinstance(d, ToolDispatchStrategy)

    def test_strategy_protocol_xml(self):
        """XmlToolDispatcher implements ToolDispatchStrategy protocol."""
        from sage.tools.dispatcher import ToolDispatchStrategy, XmlToolDispatcher

        d = XmlToolDispatcher()
        assert isinstance(d, ToolDispatchStrategy)

    def test_strategy_protocol_has_prepare_tools(self):
        """Both dispatchers have prepare_tools method."""
        from sage.tools.dispatcher import NativeToolDispatcher, XmlToolDispatcher

        for cls in (NativeToolDispatcher, XmlToolDispatcher):
            d = cls()
            assert hasattr(d, "prepare_tools")
            assert callable(d.prepare_tools)

    def test_strategy_protocol_has_parse_response(self):
        """Both dispatchers have parse_response method."""
        from sage.tools.dispatcher import NativeToolDispatcher, XmlToolDispatcher

        for cls in (NativeToolDispatcher, XmlToolDispatcher):
            d = cls()
            assert hasattr(d, "parse_response")
            assert callable(d.parse_response)

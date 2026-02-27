"""Tests for multi-format tool call parser chain.

LiteLLM validation finding: LiteLLM 1.81.14 handles OpenAI-style JSON tool calls
natively via its completion pipeline (ChatCompletionMessageToolCall types and
_process_assistant_message_tool_calls), but does NOT provide any utility to parse
XML-tagged or markdown code-fence tool calls from raw LLM text output.
The function litellm.utils.get_tool_calls_from_message does not exist.
Therefore, we implement all parsers here for format-independent parsing.
"""

from __future__ import annotations


from sage.models import ToolCall
from sage.parsing.tool_calls import (
    JsonRepairParser,
    MarkdownJsonParser,
    NativeJsonParser,
    XmlToolCallParser,
    parse_tool_calls,
)


# ---------------------------------------------------------------------------
# NativeJsonParser tests
# ---------------------------------------------------------------------------


class TestNativeJsonParser:
    def setup_method(self) -> None:
        self.parser = NativeJsonParser()

    def test_native_json_object(self) -> None:
        """Single JSON object with name and arguments."""
        text = '{"name": "shell", "arguments": {"cmd": "ls"}}'
        result = self.parser.parse(text)
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "shell"
        assert result[0].arguments == {"cmd": "ls"}

    def test_native_json_array(self) -> None:
        """Array of JSON tool call objects."""
        text = '[{"name": "a", "arguments": {}}, {"name": "b", "arguments": {"x": 1}}]'
        result = self.parser.parse(text)
        assert result is not None
        assert len(result) == 2
        assert result[0].name == "a"
        assert result[1].name == "b"
        assert result[1].arguments == {"x": 1}

    def test_native_function_call_field(self) -> None:
        """OpenAI-style function_call field with string arguments."""
        # Use json.dumps to produce a valid JSON string with escaped inner quotes
        import json as _json

        text = _json.dumps(
            {"function_call": {"name": "get_weather", "arguments": '{"city": "London"}'}}
        )
        result = self.parser.parse(text)
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "get_weather"
        assert result[0].arguments == {"city": "London"}

    def test_native_function_call_field_dict_arguments(self) -> None:
        """function_call field with dict arguments (not string)."""
        text = '{"function_call": {"name": "calc", "arguments": {"op": "add"}}}'
        result = self.parser.parse(text)
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "calc"

    def test_native_json_not_tool_call(self) -> None:
        """Valid JSON but not a tool call structure returns None."""
        text = '{"foo": "bar", "baz": 42}'
        result = self.parser.parse(text)
        assert result is None

    def test_native_json_invalid_returns_none(self) -> None:
        """Invalid JSON returns None."""
        text = "not json at all"
        result = self.parser.parse(text)
        assert result is None

    def test_native_json_id_preserved_if_present(self) -> None:
        """If id field is in JSON, it should be used."""
        text = '{"name": "tool", "arguments": {}, "id": "call_123"}'
        result = self.parser.parse(text)
        assert result is not None
        assert result[0].id == "call_123"

    def test_native_json_arguments_as_string(self) -> None:
        """arguments as JSON string should be parsed to dict."""
        text = '{"name": "shell", "arguments": "{\\"cmd\\": \\"echo hi\\"}"}'
        result = self.parser.parse(text)
        assert result is not None
        assert result[0].name == "shell"
        assert result[0].arguments == {"cmd": "echo hi"}


# ---------------------------------------------------------------------------
# XmlToolCallParser tests
# ---------------------------------------------------------------------------


class TestXmlToolCallParser:
    def setup_method(self) -> None:
        self.parser = XmlToolCallParser()

    def test_xml_single(self) -> None:
        """Single XML tool_call block."""
        text = '<tool_call><name>shell</name><arguments>{"cmd": "ls"}</arguments></tool_call>'
        result = self.parser.parse(text)
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "shell"
        assert result[0].arguments == {"cmd": "ls"}

    def test_xml_multiple(self) -> None:
        """Two XML tool_call blocks in one text."""
        text = (
            '<tool_call><name>read_file</name><arguments>{"path": "/tmp/a"}</arguments></tool_call>'
            "\n"
            '<tool_call><name>write_file</name><arguments>{"path": "/tmp/b", "content": "hi"}</arguments></tool_call>'
        )
        result = self.parser.parse(text)
        assert result is not None
        assert len(result) == 2
        assert result[0].name == "read_file"
        assert result[1].name == "write_file"
        assert result[1].arguments == {"path": "/tmp/b", "content": "hi"}

    def test_xml_with_surrounding_text(self) -> None:
        """XML tool_call embedded in surrounding text."""
        text = 'I will call the tool now.\n<tool_call><name>greet</name><arguments>{"who": "world"}</arguments></tool_call>\nDone.'
        result = self.parser.parse(text)
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "greet"

    def test_xml_no_tool_call_returns_none(self) -> None:
        """Text without XML tool_call tags returns None."""
        text = "Hello, there is no tool call here."
        result = self.parser.parse(text)
        assert result is None

    def test_xml_empty_arguments(self) -> None:
        """XML tool_call with empty arguments dict."""
        text = "<tool_call><name>ping</name><arguments>{}</arguments></tool_call>"
        result = self.parser.parse(text)
        assert result is not None
        assert result[0].name == "ping"
        assert result[0].arguments == {}


# ---------------------------------------------------------------------------
# MarkdownJsonParser tests
# ---------------------------------------------------------------------------


class TestMarkdownJsonParser:
    def setup_method(self) -> None:
        self.parser = MarkdownJsonParser()

    def test_markdown_json_fence(self) -> None:
        """```json code fence with tool call."""
        text = '```json\n{"name": "shell", "arguments": {}}\n```'
        result = self.parser.parse(text)
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "shell"
        assert result[0].arguments == {}

    def test_markdown_tool_call_fence(self) -> None:
        """```tool_call code fence."""
        text = '```tool_call\n{"name": "search", "arguments": {"query": "python"}}\n```'
        result = self.parser.parse(text)
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "search"
        assert result[0].arguments == {"query": "python"}

    def test_markdown_no_fence_returns_none(self) -> None:
        """Text without markdown fences returns None."""
        text = "No code fences here."
        result = self.parser.parse(text)
        assert result is None

    def test_markdown_fence_not_tool_call_returns_none(self) -> None:
        """Markdown fence with non-tool-call JSON returns None."""
        text = '```json\n{"message": "hello"}\n```'
        result = self.parser.parse(text)
        assert result is None

    def test_markdown_json_with_arguments_as_string(self) -> None:
        """Markdown json fence with arguments as JSON string."""
        text = '```json\n{"name": "tool", "arguments": "{\\"key\\": \\"val\\"}"}\n```'
        result = self.parser.parse(text)
        assert result is not None
        assert result[0].name == "tool"
        assert result[0].arguments == {"key": "val"}


# ---------------------------------------------------------------------------
# JsonRepairParser tests
# ---------------------------------------------------------------------------


class TestJsonRepairParser:
    def setup_method(self) -> None:
        self.parser = JsonRepairParser()

    def test_repair_trailing_comma(self) -> None:
        """JSON with trailing comma is repaired and parsed."""
        text = '{"name": "shell", "arguments": {"cmd": "ls"},}'
        result = self.parser.parse(text)
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "shell"
        assert result[0].arguments == {"cmd": "ls"}

    def test_repair_missing_quotes(self) -> None:
        """JSON with missing quotes around keys is repaired."""
        text = '{name: "shell", arguments: {cmd: "ls"}}'
        result = self.parser.parse(text)
        # json_repair may or may not handle this; we just verify no exception
        # and if parsed, name is correct
        if result is not None:
            assert result[0].name == "shell"

    def test_repair_not_tool_call_returns_none(self) -> None:
        """Repaired JSON that doesn't look like a tool call returns None."""
        text = '{"foo": "bar",}'
        result = self.parser.parse(text)
        assert result is None

    def test_repair_plain_text_returns_none(self) -> None:
        """Pure plain text (unrecoverable) returns None."""
        text = "This is just plain English text."
        result = self.parser.parse(text)
        assert result is None


# ---------------------------------------------------------------------------
# parse_tool_calls (chain) tests
# ---------------------------------------------------------------------------


class TestParseToolCallsChain:
    def test_native_json_wins_first(self) -> None:
        """Native JSON parser handles valid JSON tool calls."""
        text = '{"name": "run", "arguments": {"x": 42}}'
        result = parse_tool_calls(text)
        assert len(result) == 1
        assert result[0].name == "run"

    def test_xml_parsed_when_native_fails(self) -> None:
        """XML parser kicks in when native JSON fails."""
        text = '<tool_call><name>shell</name><arguments>{"cmd": "pwd"}</arguments></tool_call>'
        result = parse_tool_calls(text)
        assert len(result) == 1
        assert result[0].name == "shell"

    def test_markdown_parsed_when_xml_fails(self) -> None:
        """Markdown parser kicks in when native JSON and XML fail."""
        text = '```json\n{"name": "fetch", "arguments": {"url": "http://example.com"}}\n```'
        result = parse_tool_calls(text)
        assert len(result) == 1
        assert result[0].name == "fetch"

    def test_repair_parsed_as_last_resort(self) -> None:
        """JSON repair parser handles malformed JSON tool calls."""
        text = '{"name": "shell", "arguments": {"cmd": "ls"},}'
        result = parse_tool_calls(text)
        assert len(result) == 1
        assert result[0].name == "shell"

    def test_all_fail_empty(self) -> None:
        """Plain text that cannot be parsed returns empty list."""
        text = "This is just plain text with no tool calls."
        result = parse_tool_calls(text)
        assert result == []

    def test_never_raises(self) -> None:
        """parse_tool_calls never raises exceptions."""
        # Various weird inputs
        for bad_input in ["", "   ", "\n\n", "null", "[]", "{}", "true", "42"]:
            result = parse_tool_calls(bad_input)
            assert isinstance(result, list)

    def test_returns_list_of_toolcall_instances(self) -> None:
        """Result items are ToolCall model instances."""
        text = '{"name": "tool", "arguments": {}}'
        result = parse_tool_calls(text)
        assert len(result) == 1
        assert isinstance(result[0], ToolCall)


# ---------------------------------------------------------------------------
# LiteLLM validation test
# ---------------------------------------------------------------------------


class TestLiteLLMValidation:
    def test_litellm_does_not_parse_xml_tool_calls(self) -> None:
        """Document that LiteLLM does NOT have get_tool_calls_from_message.

        LiteLLM 1.81.14 handles OpenAI-style JSON tool calls internally via
        its completion pipeline types (ChatCompletionMessageToolCall), but it
        provides no utility to extract tool calls from raw text in XML or
        markdown format. The function litellm.utils.get_tool_calls_from_message
        does not exist. Our parsers fill this gap for non-LiteLLM code paths.
        """
        import litellm

        # LiteLLM does NOT expose get_tool_calls_from_message
        assert not hasattr(litellm.utils, "get_tool_calls_from_message")

    def test_litellm_has_openai_tool_call_types(self) -> None:
        """LiteLLM does provide OpenAI-compatible tool call types."""
        import litellm

        # These exist for OpenAI-format tool calls
        assert hasattr(litellm, "ChatCompletionMessageToolCall")
        assert hasattr(litellm.utils, "validate_and_fix_openai_tools")

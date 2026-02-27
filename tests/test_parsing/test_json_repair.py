"""Tests for sage.parsing.json_repair."""

from __future__ import annotations


from sage.parsing.json_repair import repair_json, try_parse_json


# ---------------------------------------------------------------------------
# repair_json tests
# ---------------------------------------------------------------------------


class TestRepairJsonTrailingCommas:
    def test_trailing_comma_object(self) -> None:
        result = repair_json('{"a": 1,}')
        import json

        assert json.loads(result) == {"a": 1}

    def test_trailing_comma_array(self) -> None:
        result = repair_json("[1, 2,]")
        import json

        assert json.loads(result) == [1, 2]

    def test_nested_repair(self) -> None:
        result = repair_json('{"a": {"b": 1,},}')
        import json

        assert json.loads(result) == {"a": {"b": 1}}


class TestRepairJsonMissingClosing:
    def test_missing_closing_brace(self) -> None:
        result = repair_json('{"a": 1')
        import json

        assert json.loads(result) == {"a": 1}

    def test_missing_closing_bracket(self) -> None:
        result = repair_json("[1, 2")
        import json

        assert json.loads(result) == [1, 2]


class TestRepairJsonCodeFences:
    def test_code_fence_stripping_with_lang(self) -> None:
        result = repair_json('```json\n{"a": 1}\n```')
        import json

        assert json.loads(result) == {"a": 1}

    def test_code_fence_no_lang(self) -> None:
        result = repair_json('```\n{"a": 1}\n```')
        import json

        assert json.loads(result) == {"a": 1}


class TestRepairJsonPassthrough:
    def test_oversized_input_passthrough(self) -> None:
        big = "x" * 200_000
        result = repair_json(big)
        assert result == big

    def test_already_valid_passthrough(self) -> None:
        valid = '{"a": 1, "b": [1, 2, 3]}'
        result = repair_json(valid)
        import json

        assert json.loads(result) == {"a": 1, "b": [1, 2, 3]}


# ---------------------------------------------------------------------------
# try_parse_json tests
# ---------------------------------------------------------------------------


class TestTryParseJson:
    def test_completely_unparseable_returns_none(self) -> None:
        result = try_parse_json("not json")
        assert result is None

    def test_valid_json_parsed_directly(self) -> None:
        result = try_parse_json('{"a": 1}')
        assert result == {"a": 1}

    def test_trailing_comma_repaired_and_parsed(self) -> None:
        result = try_parse_json('{"a": 1, "b": 2,}')
        assert result == {"a": 1, "b": 2}

    def test_missing_brace_repaired_and_parsed(self) -> None:
        result = try_parse_json('{"a": 1')
        assert result == {"a": 1}

    def test_code_fence_repaired_and_parsed(self) -> None:
        result = try_parse_json('```json\n{"a": 1}\n```')
        assert result == {"a": 1}

    def test_array_parsed(self) -> None:
        result = try_parse_json("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_oversized_unparseable_returns_none(self) -> None:
        big = "x" * 200_000
        result = try_parse_json(big)
        assert result is None

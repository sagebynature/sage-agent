"""Tests for the @tool decorator and schema generation."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from sage.models import ToolSchema
from sage.tools.decorator import tool


class SearchQuery(BaseModel):
    """A search query with filters."""

    query: str
    limit: int = 10


class TestToolDecorator:
    """Tests for @tool schema generation."""

    def test_simple_function(self) -> None:
        @tool
        def search(query: str, max_results: int) -> str:
            """Search the web."""
            return ""

        schema: ToolSchema = search.__tool_schema__
        assert schema.name == "search"
        assert schema.description == "Search the web."
        assert schema.parameters["properties"]["query"] == {"type": "string"}
        assert schema.parameters["properties"]["max_results"] == {"type": "integer"}
        assert schema.parameters["required"] == ["query", "max_results"]
        assert schema.metadata is None

    def test_optional_parameter_with_default(self) -> None:
        @tool
        def greet(name: str, greeting: str = "Hello") -> str:
            """Greet someone."""
            return f"{greeting}, {name}!"

        schema: ToolSchema = greet.__tool_schema__
        assert "name" in schema.parameters["required"]
        assert "greeting" not in schema.parameters["required"]
        assert schema.parameters["properties"]["greeting"]["default"] == "Hello"

    def test_optional_type_hint(self) -> None:
        @tool
        def lookup(key: str, fallback: Optional[str] = None) -> str:
            """Look up a key."""
            return ""

        schema: ToolSchema = lookup.__tool_schema__
        assert schema.parameters["required"] == ["key"]
        assert schema.parameters["properties"]["fallback"] == {
            "type": "string",
            "default": None,
        }

    def test_no_params(self) -> None:
        @tool
        def noop() -> None:
            """Do nothing."""

        schema: ToolSchema = noop.__tool_schema__
        assert schema.parameters["properties"] == {}
        assert "required" not in schema.parameters

    def test_async_function(self) -> None:
        @tool
        async def fetch(url: str) -> str:
            """Fetch a URL."""
            return ""

        schema: ToolSchema = fetch.__tool_schema__
        assert schema.name == "fetch"
        assert schema.parameters["required"] == ["url"]

    def test_pydantic_model_parameter(self) -> None:
        @tool
        def run_search(query: SearchQuery) -> str:
            """Run a search with structured query."""
            return ""

        schema: ToolSchema = run_search.__tool_schema__
        query_prop = schema.parameters["properties"]["query"]
        # Should use Pydantic's model_json_schema output.
        assert query_prop["type"] == "object"
        assert "properties" in query_prop
        assert "query" in query_prop["properties"]

    def test_docstring_becomes_description(self) -> None:
        @tool
        def helper(x: int) -> int:
            """This is the description."""
            return x

        assert helper.__tool_schema__.description == "This is the description."

    def test_no_docstring(self) -> None:
        @tool
        def bare(x: int) -> int:
            return x

        assert bare.__tool_schema__.description == ""

    def test_function_unchanged(self) -> None:
        """The decorator should not wrap or alter the function."""

        @tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        assert add(1, 2) == 3

    def test_bool_and_float_types(self) -> None:
        @tool
        def configure(ratio: float, verbose: bool) -> str:
            """Configure settings."""
            return ""

        schema: ToolSchema = configure.__tool_schema__
        assert schema.parameters["properties"]["ratio"] == {"type": "number"}
        assert schema.parameters["properties"]["verbose"] == {"type": "boolean"}

    def test_list_and_dict_types(self) -> None:
        @tool
        def process(items: list[str], metadata: dict[str, int]) -> str:
            """Process items."""
            return ""

        schema: ToolSchema = process.__tool_schema__
        assert schema.parameters["properties"]["items"] == {
            "type": "array",
            "items": {"type": "string"},
        }
        assert schema.parameters["properties"]["metadata"] == {
            "type": "object",
            "additionalProperties": {"type": "integer"},
        }

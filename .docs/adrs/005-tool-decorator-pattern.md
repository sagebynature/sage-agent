# ADR-005: @tool Decorator Pattern

## Status
Accepted

## Context
The SDK needs a way for users to define custom tools that agents can invoke. The tool definition mechanism must generate the JSON schema required by LLM function-calling APIs, support type-safe arguments, and minimize boilerplate.

Alternatives considered included manual schema dictionaries, class-based tool definitions only, and external schema files.

## Decision
Use a `@tool` decorator that inspects function signatures and type hints to auto-generate `ToolSchema` objects. The decorator:

- Reads the function name as the tool name
- Uses the docstring as the tool description
- Maps Python type annotations to JSON Schema types
- Supports `str`, `int`, `float`, `bool`, `list[T]`, `dict[K, V]`, `Optional[T]`, and Pydantic models
- Works with both sync and async functions
- Attaches the schema as `__tool_schema__` on the function

```python
@tool
def calculate(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))
```

For stateful tools, `ToolBase` provides lifecycle hooks (`setup`/`teardown`) and auto-collects `@tool`-decorated methods.

## Consequences
**Positive:**
- Minimal boilerplate: one decorator and type hints are sufficient
- Pythonic API familiar to users of FastAPI and similar frameworks
- Type hints serve double duty as documentation and schema generation
- Pydantic model support enables complex structured arguments
- Sync functions are automatically wrapped in `asyncio.to_thread`

**Negative:**
- Limited to Python (tools cannot be defined in other languages natively)
- Complex generic types may not map cleanly to JSON Schema
- Runtime introspection is less transparent than explicit schema files

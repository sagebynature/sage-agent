"""@tool decorator for automatic ToolSchema generation from function signatures."""

from __future__ import annotations

import inspect
import types
import typing
from typing import Any, Callable, Union, get_args, get_origin

from pydantic import BaseModel

from sage.models import ToolSchema

# Mapping from Python types to JSON Schema types.
_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _is_optional(annotation: Any) -> tuple[bool, Any]:
    """Check if a type annotation is Optional[X] and return (is_optional, inner_type).

    Optional[X] is equivalent to Union[X, None].
    """
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1 and len(args) == 2:
            return True, non_none[0]
    return False, annotation


def _annotation_to_json_schema(annotation: Any) -> dict[str, Any]:
    """Convert a Python type annotation to a JSON Schema dict."""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {"type": "string"}

    # Handle Optional[X] — unwrap and recurse.
    is_opt, inner = _is_optional(annotation)
    if is_opt:
        return _annotation_to_json_schema(inner)

    # Pydantic model — use its JSON schema.
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation.model_json_schema()

    # Generic types like list[str], dict[str, int].
    origin = get_origin(annotation)
    if origin is list:
        args = get_args(annotation)
        schema: dict[str, Any] = {"type": "array"}
        if args:
            schema["items"] = _annotation_to_json_schema(args[0])
        return schema
    if origin is dict:
        args = get_args(annotation)
        schema = {"type": "object"}
        if args and len(args) == 2:
            schema["additionalProperties"] = _annotation_to_json_schema(args[1])
        return schema

    # Direct type lookup.
    json_type = _TYPE_MAP.get(annotation)
    if json_type:
        return {"type": json_type}

    # Fallback.
    return {"type": "string"}


def tool(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorate a function to generate and attach a ToolSchema.

    The decorator inspects the function's signature, type hints, and docstring
    to produce a ``ToolSchema`` stored as ``fn.__tool_schema__``.  The function
    itself is returned unchanged — it is **not** wrapped or made async.
    """
    sig = inspect.signature(fn)
    description = inspect.getdoc(fn) or ""

    # Resolve string annotations from `from __future__ import annotations`.
    try:
        hints = typing.get_type_hints(fn)
    except Exception:
        hints = {}

    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name == "self":
            continue

        annotation = hints.get(name, param.annotation)
        prop = _annotation_to_json_schema(annotation)

        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
        else:
            is_opt, _ = _is_optional(annotation)
            if not is_opt:
                required.append(name)

        properties[name] = prop

    parameters: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required

    schema = ToolSchema(
        name=fn.__name__,
        description=description,
        parameters=parameters,
    )

    fn.__tool_schema__ = schema  # type: ignore[attr-defined]
    return fn

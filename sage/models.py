"""Core data models for Sage."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Represents a tool/function call made by the model."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    """Token usage information from a completion."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Message(BaseModel):
    """A single message in a conversation."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class CompletionResult(BaseModel):
    """Result from a non-streaming completion request."""

    message: Message
    usage: Usage = Field(default_factory=Usage)
    raw_response: object = None


class StreamChunk(BaseModel):
    """A single chunk from a streaming completion.

    For text-only chunks, ``delta`` holds the content fragment.
    When ``finish_reason`` is ``"tool_calls"``, the ``tool_calls`` field
    carries the fully-assembled tool call list for that streaming turn.
    """

    delta: str | None = None
    finish_reason: str | None = None
    tool_calls: list[ToolCall] | None = None
    usage: Usage | None = None


class ToolSchema(BaseModel):
    """Schema definition for a tool that can be passed to the model."""

    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)

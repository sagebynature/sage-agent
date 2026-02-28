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
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    reasoning_tokens: int = 0
    cost: float = 0.0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            cost=self.cost + other.cost,
        )

    def __iadd__(self, other: "Usage") -> "Usage":
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_creation_tokens += other.cache_creation_tokens
        self.reasoning_tokens += other.reasoning_tokens
        self.cost += other.cost
        return self


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

"""Tests for credential scrubbing hook — TDD, written before implementation."""

from __future__ import annotations

import time
from typing import Any

import pytest

from sage.hooks.base import HookEvent
from sage.hooks.builtin.credential_scrubber import make_credential_scrubber, scrub_text


class TestScrubText:
    """Unit tests for scrub_text()."""

    def test_api_key_scrubbed(self) -> None:
        """OpenAI-style sk- key is redacted."""
        result = scrub_text("key is sk-abc123def456ghi789jkl012")
        assert "REDACTED" in result
        # Full key suffix must not appear
        assert "abc123def456ghi789jkl012" not in result

    def test_bearer_token_scrubbed(self) -> None:
        """Bearer token is redacted."""
        text = "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
        result = scrub_text(text)
        assert "REDACTED" in result
        assert "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9" not in result

    def test_aws_key_scrubbed(self) -> None:
        """AWS-style AKIA access key is redacted."""
        text = "AWS key: AKIAIOSFODNN7EXAMPLE"
        result = scrub_text(text)
        assert "REDACTED" in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_generic_key_value_secret_scrubbed(self) -> None:
        """Generic key=value patterns like password=hunter2 are redacted."""
        text = "password=supersecretvalue123"
        result = scrub_text(text)
        assert "REDACTED" in result

    def test_generic_token_colon_scrubbed(self) -> None:
        """token: <value> pattern is redacted."""
        text = "token: myverysecrettoken123"
        result = scrub_text(text)
        assert "REDACTED" in result

    def test_uuid_preserved(self) -> None:
        """UUIDs must NOT be redacted (allowlist)."""
        uuid_text = "ID: 550e8400-e29b-41d4-a716-446655440000"
        result = scrub_text(uuid_text)
        assert result == uuid_text

    def test_sha1_hash_preserved(self) -> None:
        """SHA-1 git commit hashes must NOT be redacted (allowlist)."""
        sha1_text = "commit: da39a3ee5e6b4b0d3255bfef95601890afd80709"
        result = scrub_text(sha1_text)
        assert result == sha1_text

    def test_sha256_hash_preserved(self) -> None:
        """SHA-256 hashes must NOT be redacted (allowlist)."""
        sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        result = scrub_text(sha256)
        assert result == sha256

    def test_prefix_preserved(self) -> None:
        """First 4 chars of the matched secret are kept in the output."""
        result = scrub_text("sk-proj-abcdefghijklmnopqrstuvwxyz1234")
        # Default preserve_prefix=4, so "sk-p" should appear
        assert "sk-p" in result
        assert "REDACTED" in result

    def test_clean_text_unchanged(self) -> None:
        """Plain text with no secrets is returned unchanged."""
        text = "The weather is nice today"
        assert scrub_text(text) == text

    def test_empty_string_unchanged(self) -> None:
        """Empty string is returned unchanged."""
        assert scrub_text("") == ""

    def test_multiple_secrets_all_scrubbed(self) -> None:
        """Multiple secrets in one string are all redacted."""
        text = "key sk-abc123def456ghi789jkl012 and aws AKIAIOSFODNN7EXAMPLE"
        result = scrub_text(text)
        assert result.count("REDACTED") >= 2

    def test_key_prefix_style(self) -> None:
        """key- prefixed tokens are redacted."""
        text = "using key-abcdefghijklmnopqrstuvwxyz12"
        result = scrub_text(text)
        assert "REDACTED" in result

    def test_performance(self) -> None:
        """1000 calls with ~100-char input must complete in under 1 second."""
        msg = "Here is key sk-abcdefghijklmnopqrstuvwxyz12 and token Bearer eyJhbGci"
        start = time.perf_counter()
        for _ in range(1000):
            scrub_text(msg)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"Performance too slow: {elapsed:.3f}s for 1000 calls"

    def test_preserve_prefix_zero(self) -> None:
        """preserve_prefix=0 replaces the entire match."""
        result = scrub_text("sk-abc123def456ghi789jkl012", preserve_prefix=0)
        assert "REDACTED" in result
        # No prefix fragment from the key should survive
        assert "sk-a" not in result

    def test_preserve_prefix_custom(self) -> None:
        """Custom preserve_prefix=6 keeps 6 chars."""
        result = scrub_text("sk-abc123def456ghi789jkl012", preserve_prefix=6)
        assert result.startswith("sk-abc")
        assert "REDACTED" in result


class TestMakeCredentialScrubber:
    """Integration tests for the hook factory."""

    async def test_hook_scrubs_output(self) -> None:
        """Hook modifies data['output'] when it contains a secret."""
        hook = make_credential_scrubber()
        data: dict[str, Any] = {"output": "API key: sk-abc123def456ghi789jkl012"}
        await hook(HookEvent.POST_TOOL_EXECUTE, data)
        assert "REDACTED" in data["output"]
        assert "abc123def456ghi789jkl012" not in data["output"]

    async def test_hook_no_op_on_clean_output(self) -> None:
        """Hook leaves clean output unchanged."""
        hook = make_credential_scrubber()
        data: dict[str, Any] = {"output": "Hello, world!"}
        await hook(HookEvent.POST_TOOL_EXECUTE, data)
        assert data["output"] == "Hello, world!"

    async def test_hook_ignores_pre_tool_execute(self) -> None:
        """Hook is a no-op for PRE_TOOL_EXECUTE events."""
        hook = make_credential_scrubber()
        data: dict[str, Any] = {"output": "sk-abc123def456ghi789jkl012"}
        await hook(HookEvent.PRE_TOOL_EXECUTE, data)
        # data should be unchanged
        assert "sk-abc123def456ghi789jkl012" in data["output"]

    async def test_hook_ignores_missing_output_key(self) -> None:
        """Hook does not crash when 'output' key is absent."""
        hook = make_credential_scrubber()
        data: dict[str, Any] = {"tool_name": "shell"}
        await hook(HookEvent.POST_TOOL_EXECUTE, data)
        assert "output" not in data

    async def test_hook_ignores_non_string_output(self) -> None:
        """Hook does not process non-string output values."""
        hook = make_credential_scrubber()
        data: dict[str, Any] = {"output": 42}
        await hook(HookEvent.POST_TOOL_EXECUTE, data)
        assert data["output"] == 42

    async def test_hook_logs_warning_on_scrub(self, caplog: pytest.LogCaptureFixture) -> None:
        """Hook emits a WARNING log when credentials are found and scrubbed."""
        import logging

        hook = make_credential_scrubber()
        data: dict[str, Any] = {"output": "sk-abc123def456ghi789jkl012"}

        with caplog.at_level(logging.WARNING, logger="sage.hooks.builtin.credential_scrubber"):
            await hook(HookEvent.POST_TOOL_EXECUTE, data)

        assert any(
            "scrubbed" in r.message.lower() or "credential" in r.message.lower()
            for r in caplog.records
        )

    async def test_hook_returns_none(self) -> None:
        """Hook is void — return value is None."""
        hook = make_credential_scrubber()
        data: dict[str, Any] = {"output": "clean text"}
        result = await hook(HookEvent.POST_TOOL_EXECUTE, data)
        assert result is None

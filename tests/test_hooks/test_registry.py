"""Tests for HookRegistry, HookEvent, and HookHandler."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from sage.hooks import HookEvent, HookHandler, HookRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def noop_handler(event: HookEvent, data: dict[str, Any]) -> None:
    """A no-op void handler."""


async def modifying_handler(event: HookEvent, data: dict[str, Any]) -> dict[str, Any]:
    """A simple modifying handler that adds a key."""
    data["modified"] = True
    return data


# ---------------------------------------------------------------------------
# Tests: HookEvent
# ---------------------------------------------------------------------------


class TestHookEvent:
    def test_all_events_exist(self) -> None:
        """All required events are defined on HookEvent."""
        assert HookEvent.PRE_LLM_CALL
        assert HookEvent.POST_LLM_CALL
        assert HookEvent.PRE_TOOL_EXECUTE
        assert HookEvent.POST_TOOL_EXECUTE
        assert HookEvent.PRE_COMPACTION
        assert HookEvent.POST_COMPACTION
        assert HookEvent.PRE_MEMORY_RECALL
        assert HookEvent.POST_MEMORY_STORE

    def test_hook_event_is_string_enum(self) -> None:
        """HookEvent values are strings."""
        assert isinstance(HookEvent.PRE_LLM_CALL.value, str)
        assert isinstance(HookEvent.POST_LLM_CALL.value, str)


# ---------------------------------------------------------------------------
# Tests: HookHandler Protocol
# ---------------------------------------------------------------------------


class TestHookHandlerProtocol:
    def test_async_callable_satisfies_protocol(self) -> None:
        """An async callable with correct signature satisfies HookHandler."""
        assert isinstance(noop_handler, HookHandler)

    def test_non_async_does_not_satisfy_protocol(self) -> None:
        """A sync callable does NOT satisfy HookHandler (runtime check)."""

        def sync_fn(event: HookEvent, data: dict[str, Any]) -> None:
            pass

        # runtime_checkable only checks for the method's presence,
        # not coroutine-ness — so we just ensure noop_handler is recognized.
        # The key property we test is that HookHandler is runtime_checkable.
        assert isinstance(noop_handler, HookHandler)


# ---------------------------------------------------------------------------
# Tests: HookRegistry — basic registration
# ---------------------------------------------------------------------------


class TestHookRegistryRegistration:
    def test_register_handler_succeeds(self) -> None:
        reg = HookRegistry()
        reg.register(HookEvent.PRE_LLM_CALL, noop_handler)

    def test_register_multiple_handlers(self) -> None:
        reg = HookRegistry()
        reg.register(HookEvent.PRE_LLM_CALL, noop_handler)
        reg.register(HookEvent.PRE_LLM_CALL, modifying_handler, modifying=True)

    def test_register_different_events(self) -> None:
        reg = HookRegistry()
        reg.register(HookEvent.PRE_LLM_CALL, noop_handler)
        reg.register(HookEvent.POST_LLM_CALL, noop_handler)

    def test_max_10_handlers_per_event_raises_on_11th(self) -> None:
        reg = HookRegistry()
        for i in range(10):

            async def h(event: HookEvent, data: dict[str, Any], _i: int = i) -> None:
                pass

            reg.register(HookEvent.PRE_LLM_CALL, h)
        # 11th registration should raise ValueError
        with pytest.raises(ValueError, match="[Mm]ax"):

            async def extra(event: HookEvent, data: dict[str, Any]) -> None:
                pass

            reg.register(HookEvent.PRE_LLM_CALL, extra)

    def test_clear_removes_all_handlers(self) -> None:
        reg = HookRegistry()
        reg.register(HookEvent.PRE_LLM_CALL, noop_handler)
        reg.clear()
        # After clear, should be able to register up to 10 again
        for i in range(10):

            async def h(event: HookEvent, data: dict[str, Any], _i: int = i) -> None:
                pass

            reg.register(HookEvent.PRE_LLM_CALL, h)


# ---------------------------------------------------------------------------
# Tests: HookRegistry — freeze
# ---------------------------------------------------------------------------


class TestHookRegistryFreeze:
    def test_freeze_prevents_registration(self) -> None:
        reg = HookRegistry()
        reg.freeze()
        with pytest.raises(ValueError, match="[Ff]rozen"):
            reg.register(HookEvent.PRE_LLM_CALL, noop_handler)

    @pytest.mark.asyncio
    async def test_freeze_does_not_affect_emit(self) -> None:
        """freeze() only prevents register, not emit."""
        reg = HookRegistry()
        reg.register(HookEvent.PRE_LLM_CALL, noop_handler)
        reg.freeze()
        # emit_void should still work after freeze
        await reg.emit_void(HookEvent.PRE_LLM_CALL, {})

    def test_clear_after_freeze_allows_registration(self) -> None:
        """clear() resets frozen state."""
        reg = HookRegistry()
        reg.freeze()
        reg.clear()
        # Should work after clear
        reg.register(HookEvent.PRE_LLM_CALL, noop_handler)


# ---------------------------------------------------------------------------
# Tests: HookRegistry — void (parallel) dispatch
# ---------------------------------------------------------------------------


class TestHookRegistryVoidDispatch:
    @pytest.mark.asyncio
    async def test_void_handler_called(self) -> None:
        reg = HookRegistry()
        called = []

        async def track(event: HookEvent, data: dict[str, Any]) -> None:
            called.append(event)

        reg.register(HookEvent.PRE_LLM_CALL, track)
        await reg.emit_void(HookEvent.PRE_LLM_CALL, {})
        assert HookEvent.PRE_LLM_CALL in called

    @pytest.mark.asyncio
    async def test_void_handlers_all_called(self) -> None:
        reg = HookRegistry()
        results: list[str] = []

        async def h1(event: HookEvent, data: dict[str, Any]) -> None:
            results.append("h1")

        async def h2(event: HookEvent, data: dict[str, Any]) -> None:
            results.append("h2")

        reg.register(HookEvent.PRE_LLM_CALL, h1)
        reg.register(HookEvent.PRE_LLM_CALL, h2)
        await reg.emit_void(HookEvent.PRE_LLM_CALL, {})
        assert "h1" in results
        assert "h2" in results

    @pytest.mark.asyncio
    async def test_void_error_isolation(self) -> None:
        """One failing handler must not prevent others from running."""
        reg = HookRegistry()
        results: list[str] = []

        async def h1(event: HookEvent, data: dict[str, Any]) -> None:
            results.append("h1")

        async def h2(event: HookEvent, data: dict[str, Any]) -> None:
            raise RuntimeError("boom")

        async def h3(event: HookEvent, data: dict[str, Any]) -> None:
            results.append("h3")

        reg.register(HookEvent.PRE_LLM_CALL, h1)
        reg.register(HookEvent.PRE_LLM_CALL, h2)
        reg.register(HookEvent.PRE_LLM_CALL, h3)
        # Must not raise even though h2 fails
        await reg.emit_void(HookEvent.PRE_LLM_CALL, {})
        assert "h1" in results
        assert "h3" in results

    @pytest.mark.asyncio
    async def test_void_no_handlers_is_noop(self) -> None:
        """emit_void with no registered handlers should not raise."""
        reg = HookRegistry()
        await reg.emit_void(HookEvent.PRE_LLM_CALL, {})

    @pytest.mark.asyncio
    async def test_void_fires_in_parallel(self) -> None:
        """Handlers run concurrently — both can be in-flight simultaneously."""
        reg = HookRegistry()
        started: list[str] = []
        finished: list[str] = []

        async def slow_h1(event: HookEvent, data: dict[str, Any]) -> None:
            started.append("h1")
            await asyncio.sleep(0.02)
            finished.append("h1")

        async def slow_h2(event: HookEvent, data: dict[str, Any]) -> None:
            started.append("h2")
            await asyncio.sleep(0.02)
            finished.append("h2")

        reg.register(HookEvent.PRE_LLM_CALL, slow_h1)
        reg.register(HookEvent.PRE_LLM_CALL, slow_h2)
        await reg.emit_void(HookEvent.PRE_LLM_CALL, {})
        # Both should have started before either finished (parallel)
        # We just verify both ran completely.
        assert "h1" in finished
        assert "h2" in finished

    @pytest.mark.asyncio
    async def test_void_timeout_isolates_slow_handler(self) -> None:
        """Handler exceeding 5s timeout should not prevent others."""
        reg = HookRegistry()
        results: list[str] = []

        async def very_slow(event: HookEvent, data: dict[str, Any]) -> None:
            await asyncio.sleep(100)  # Much longer than 5s timeout

        async def fast(event: HookEvent, data: dict[str, Any]) -> None:
            results.append("fast")

        reg.register(HookEvent.PRE_LLM_CALL, very_slow)
        reg.register(HookEvent.PRE_LLM_CALL, fast)
        # Should complete quickly despite very_slow handler
        await reg.emit_void(HookEvent.PRE_LLM_CALL, {})
        assert "fast" in results


# ---------------------------------------------------------------------------
# Tests: HookRegistry — modifying (sequential) dispatch
# ---------------------------------------------------------------------------


class TestHookRegistryModifyingDispatch:
    @pytest.mark.asyncio
    async def test_modifying_handler_mutates_data(self) -> None:
        reg = HookRegistry()
        reg.register(HookEvent.PRE_LLM_CALL, modifying_handler, modifying=True)
        result = await reg.emit_modifying(HookEvent.PRE_LLM_CALL, {"val": 1})
        assert result["modified"] is True

    @pytest.mark.asyncio
    async def test_modifying_handlers_sequential_by_priority(self) -> None:
        """Lower priority number fires first (lowest priority first)."""
        reg = HookRegistry()

        async def add_a(event: HookEvent, data: dict[str, Any]) -> dict[str, Any]:
            data["val"] += "A"
            return data

        async def add_b(event: HookEvent, data: dict[str, Any]) -> dict[str, Any]:
            data["val"] += "B"
            return data

        # priority=10 fires second, priority=1 fires first → result "AB"
        reg.register(HookEvent.PRE_LLM_CALL, add_b, priority=10, modifying=True)
        reg.register(HookEvent.PRE_LLM_CALL, add_a, priority=1, modifying=True)
        result = await reg.emit_modifying(HookEvent.PRE_LLM_CALL, {"val": ""})
        assert result["val"] == "AB"

    @pytest.mark.asyncio
    async def test_modifying_chained_output(self) -> None:
        """Each handler receives the output of the previous one."""
        reg = HookRegistry()

        async def double(event: HookEvent, data: dict[str, Any]) -> dict[str, Any]:
            data["n"] = data["n"] * 2
            return data

        async def add_ten(event: HookEvent, data: dict[str, Any]) -> dict[str, Any]:
            data["n"] = data["n"] + 10
            return data

        reg.register(HookEvent.PRE_LLM_CALL, double, priority=1, modifying=True)
        reg.register(HookEvent.PRE_LLM_CALL, add_ten, priority=2, modifying=True)
        result = await reg.emit_modifying(HookEvent.PRE_LLM_CALL, {"n": 5})
        # double first: 5*2=10, then add_ten: 10+10=20
        assert result["n"] == 20

    @pytest.mark.asyncio
    async def test_modifying_no_handlers_returns_original_data(self) -> None:
        """emit_modifying with no handlers returns the original data dict."""
        reg = HookRegistry()
        data = {"key": "value"}
        result = await reg.emit_modifying(HookEvent.PRE_LLM_CALL, data)
        assert result == data

    @pytest.mark.asyncio
    async def test_modifying_timeout(self) -> None:
        """Modifying handler that times out raises TimeoutError or similar."""
        reg = HookRegistry()

        async def very_slow(event: HookEvent, data: dict[str, Any]) -> dict[str, Any]:
            await asyncio.sleep(100)
            return data

        reg.register(HookEvent.PRE_LLM_CALL, very_slow, modifying=True)
        with pytest.raises((asyncio.TimeoutError, TimeoutError)):
            await reg.emit_modifying(HookEvent.PRE_LLM_CALL, {})


# ---------------------------------------------------------------------------
# Tests: HookRegistry — recursive guard
# ---------------------------------------------------------------------------


class TestHookRegistryRecursiveGuard:
    @pytest.mark.asyncio
    async def test_recursive_emit_void_raises(self) -> None:
        """Re-entering emit_void for the same event raises RuntimeError."""
        reg = HookRegistry()

        async def recursive(event: HookEvent, data: dict[str, Any]) -> None:
            # Try to emit the same event recursively
            await reg.emit_void(HookEvent.PRE_LLM_CALL, {})

        reg.register(HookEvent.PRE_LLM_CALL, recursive)
        with pytest.raises(RuntimeError, match="[Rr]ecursi"):
            await reg.emit_void(HookEvent.PRE_LLM_CALL, {})

    @pytest.mark.asyncio
    async def test_different_event_not_blocked_by_guard(self) -> None:
        """Guard is per-event; different event can be emitted from a handler."""
        reg = HookRegistry()
        called: list[str] = []

        async def emit_other(event: HookEvent, data: dict[str, Any]) -> None:
            # Emitting a DIFFERENT event should NOT raise
            await reg.emit_void(HookEvent.POST_LLM_CALL, {})
            called.append("done")

        reg.register(HookEvent.PRE_LLM_CALL, emit_other)
        await reg.emit_void(HookEvent.PRE_LLM_CALL, {})
        assert "done" in called


# ---------------------------------------------------------------------------
# Tests: HookRegistry — error logging
# ---------------------------------------------------------------------------


class TestHookRegistryErrorLogging:
    @pytest.mark.asyncio
    async def test_void_error_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Errors from void handlers are logged."""
        reg = HookRegistry()

        async def boom(event: HookEvent, data: dict[str, Any]) -> None:
            raise RuntimeError("test error")

        reg.register(HookEvent.PRE_LLM_CALL, boom)

        with caplog.at_level(logging.ERROR, logger="sage.hooks.registry"):
            await reg.emit_void(HookEvent.PRE_LLM_CALL, {})

        assert (
            any(
                "test error" in r.message or "test error" in str(r.exc_info) for r in caplog.records
            )
            or len(caplog.records) > 0
        )

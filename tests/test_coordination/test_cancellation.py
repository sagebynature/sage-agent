"""Tests for CancellationToken — Task 2."""

from __future__ import annotations

import asyncio

import pytest

from sage.coordination.cancellation import CancellationToken
from sage.exceptions import CancelledError


class TestCancellationTokenBasics:
    def test_initial_state_not_cancelled(self) -> None:
        token = CancellationToken()
        assert token.is_cancelled is False

    def test_cancel_sets_cancelled(self) -> None:
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled is True

    def test_cancel_is_idempotent(self) -> None:
        token = CancellationToken()
        token.cancel()
        token.cancel()  # Should not raise
        assert token.is_cancelled is True

    def test_raise_if_cancelled_does_nothing_when_not_cancelled(self) -> None:
        token = CancellationToken()
        token.raise_if_cancelled()  # Should not raise

    def test_raise_if_cancelled_raises_when_cancelled(self) -> None:
        token = CancellationToken()
        token.cancel()
        with pytest.raises(CancelledError):
            token.raise_if_cancelled()

    def test_cancelled_error_is_subclass_of_sage_error(self) -> None:
        from sage.exceptions import SageError

        assert issubclass(CancelledError, SageError)

    def test_cancelled_error_is_subclass_of_exception(self) -> None:
        assert issubclass(CancelledError, Exception)


class TestCancellationTokenAsync:
    @pytest.mark.asyncio
    async def test_wait_for_cancellation_completes_after_cancel(self) -> None:
        token = CancellationToken()

        async def cancel_soon() -> None:
            await asyncio.sleep(0.05)
            token.cancel()

        asyncio.create_task(cancel_soon())
        await token.wait_for_cancellation()
        assert token.is_cancelled is True

    @pytest.mark.asyncio
    async def test_wrap_returns_result_when_coroutine_completes_first(self) -> None:
        token = CancellationToken()

        async def fast() -> str:
            return "done"

        result = await token.wrap(fast())
        assert result == "done"

    @pytest.mark.asyncio
    async def test_wrap_raises_cancelled_error_when_token_cancelled_first(self) -> None:
        token = CancellationToken()

        async def slow() -> None:
            await asyncio.sleep(10)

        loop = asyncio.get_event_loop()
        loop.call_later(0.05, token.cancel)

        with pytest.raises(CancelledError):
            await token.wrap(slow())

    @pytest.mark.asyncio
    async def test_wrap_with_already_cancelled_token_raises_immediately(self) -> None:
        token = CancellationToken()
        token.cancel()

        async def slow() -> None:
            await asyncio.sleep(10)

        with pytest.raises(CancelledError):
            await token.wrap(slow())

    @pytest.mark.asyncio
    async def test_wrap_returns_correct_value_for_complex_coroutine(self) -> None:
        token = CancellationToken()

        async def compute(x: int, y: int) -> int:
            await asyncio.sleep(0.01)
            return x + y

        result = await token.wrap(compute(3, 4))
        assert result == 7

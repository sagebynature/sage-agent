"""CancellationToken for cooperative async cancellation."""

from __future__ import annotations

import asyncio
from typing import Any, Coroutine, TypeVar

from sage.exceptions import CancelledError

T = TypeVar("T")


class CancellationToken:
    """A cooperative cancellation token backed by an asyncio.Event.

    Usage::

        token = CancellationToken()

        async def main():
            # Cancel from elsewhere:
            loop.call_later(1.0, token.cancel)
            try:
                result = await token.wrap(some_coroutine())
            except CancelledError:
                print("cancelled")
    """

    def __init__(self) -> None:
        self._event: asyncio.Event = asyncio.Event()

    def cancel(self) -> None:
        """Signal cancellation. Idempotent."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """True if this token has been cancelled."""
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        """Raise CancelledError if the token has been cancelled."""
        if self.is_cancelled:
            raise CancelledError("Operation was cancelled")

    async def wait_for_cancellation(self) -> None:
        """Await until the token is cancelled."""
        await self._event.wait()

    async def wrap(self, coro: Coroutine[Any, Any, T]) -> T:
        """Run *coro* racing against cancellation.

        Returns the coroutine's result if it completes first.
        Raises CancelledError if the token is cancelled first (or already cancelled).
        """
        if self.is_cancelled:
            coro.close()
            raise CancelledError("Operation was cancelled before it started")

        coro_task: asyncio.Task[T] = asyncio.ensure_future(coro)
        cancel_task: asyncio.Task[None] = asyncio.ensure_future(self.wait_for_cancellation())

        done, pending = await asyncio.wait(
            [coro_task, cancel_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel whatever is still pending
        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        if cancel_task in done and coro_task not in done:
            # Cancellation won the race
            raise CancelledError("Operation was cancelled")

        if coro_task in done:
            # Coroutine completed — may still re-raise if it raised an exception
            return coro_task.result()

        # Both somehow not done — shouldn't happen, but be safe
        raise CancelledError("Operation was cancelled")

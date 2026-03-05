"""Hook registry for registering and dispatching hook handlers."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from sage.hooks.base import HookEvent, HookHandler

logger = logging.getLogger(__name__)

_MAX_HANDLERS_PER_EVENT = 10
_HANDLER_TIMEOUT_SECONDS = 5.0


class _RecursiveEmitError(RuntimeError):
    """Internal sentinel raised when a recursive emit is detected.

    Using a private subclass of ``RuntimeError`` lets ``_run_with_timeout``
    distinguish recursive-guard violations (which must propagate) from
    ordinary ``RuntimeError`` exceptions raised by user handlers (which must
    be caught and logged for error-isolation).
    """


@dataclass
class _HandlerEntry:
    handler: HookHandler
    priority: int
    modifying: bool


class HookRegistry:
    """Central registry for hook handlers.

    Handlers are partitioned into two classes:

    * **Void** handlers — side-effect only, fired in *parallel* via
      ``asyncio.gather``.  Per-handler errors are caught and logged so
      that one failing handler never blocks the others.

    * **Modifying** handlers — receive and return a data dict, fired
      *sequentially* in ascending priority order so that each handler
      sees the output of its predecessor.

    Safety guardrails
    -----------------
    * At most *max_handlers* (default 10) handlers per event.
    * ``freeze()`` locks the registry against further registration.
    * A recursive-emit guard raises ``RuntimeError`` if the same event
      is emitted from within one of its own handlers.
    """

    def __init__(
        self,
        max_handlers: int = _MAX_HANDLERS_PER_EVENT,
        handler_timeout: float = _HANDLER_TIMEOUT_SECONDS,
    ) -> None:
        self._max_handlers: int = max_handlers
        self._handler_timeout: float = handler_timeout
        self._handlers: dict[HookEvent, list[_HandlerEntry]] = {event: [] for event in HookEvent}
        self._frozen: bool = False
        # Tracks which events are currently being emitted (recursive guard).
        self._emitting: set[HookEvent] = set()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        event: HookEvent,
        handler: HookHandler,
        *,
        priority: int = 0,
        modifying: bool = False,
    ) -> None:
        """Register *handler* for *event*.

        Parameters
        ----------
        event:
            The ``HookEvent`` to listen on.
        handler:
            An async callable satisfying the ``HookHandler`` protocol.
        priority:
            Ordering key for modifying handlers (lower fires first).
            Ignored for void handlers.
        modifying:
            If ``True``, the handler is expected to return the (mutated)
            data dict and will be fired sequentially.
        """
        if self._frozen:
            raise ValueError("HookRegistry is frozen — no further registration allowed.")
        entries = self._handlers[event]
        if len(entries) >= self._max_handlers:
            raise ValueError(
                f"Max {self._max_handlers} handlers per event reached for "
                f"{event!r}. Cannot register more."
            )
        entries.append(_HandlerEntry(handler=handler, priority=priority, modifying=modifying))

    # ------------------------------------------------------------------
    # Dispatch: void (parallel)
    # ------------------------------------------------------------------

    async def emit_void(self, event: HookEvent, data: dict[str, Any]) -> None:
        """Fire all non-modifying handlers for *event* in parallel.

        Errors from individual handlers are caught and logged; they do
        not propagate.  Handlers that exceed the per-handler timeout are
        cancelled and treated as errors.

        Raises ``RuntimeError`` if the same event is already being emitted
        (recursive guard).
        """
        if event in self._emitting:
            raise _RecursiveEmitError(
                f"Recursive emit detected for event {event!r}. "
                "Cannot re-enter emit_void for the same event."
            )

        void_entries = [e for e in self._handlers[event] if not e.modifying]
        if not void_entries:
            return

        self._emitting.add(event)
        try:
            results = await asyncio.gather(
                *[self._run_with_timeout(entry.handler, event, data) for entry in void_entries],
                return_exceptions=True,
            )
        finally:
            self._emitting.discard(event)

        # Re-raise the recursive-guard error if any handler triggered it.
        # We use a private subclass so we never accidentally swallow an
        # ordinary RuntimeError raised by user code.
        for res in results:
            if isinstance(res, _RecursiveEmitError):
                raise RuntimeError(str(res)) from res

    async def _run_with_timeout(
        self,
        handler: HookHandler,
        event: HookEvent,
        data: dict[str, Any],
    ) -> None:
        """Run *handler* with a per-handler timeout; log non-guard exceptions."""
        try:
            await asyncio.wait_for(
                handler(event, data),
                timeout=self._handler_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Hook handler %r timed out after %ss for event %r",
                handler,
                self._handler_timeout,
                event,
            )
        except _RecursiveEmitError:
            # Propagate the recursive-guard sentinel; gather captures it and
            # emit_void will re-raise it as a plain RuntimeError.
            raise
        except Exception as exc:
            logger.error(
                "Hook handler %r raised an error for event %r: %s",
                handler,
                event,
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Dispatch: modifying (sequential)
    # ------------------------------------------------------------------

    async def emit_modifying(self, event: HookEvent, data: dict[str, Any]) -> dict[str, Any]:
        """Fire all modifying handlers for *event* sequentially by priority.

        Each handler receives the output dict of the previous handler.
        Returns the final data dict.

        Per-handler timeout of 5 seconds; a ``TimeoutError`` propagates
        to the caller for modifying handlers (unlike void handlers, we
        cannot safely skip them and continue since the data chain is broken).

        Raises ``RuntimeError`` if the same event is already being emitted.
        """
        if event in self._emitting:
            raise RuntimeError(
                f"Recursive emit detected for event {event!r}. "
                "Cannot re-enter emit_modifying for the same event."
            )

        modifying_entries = sorted(
            [e for e in self._handlers[event] if e.modifying],
            key=lambda e: e.priority,
        )
        if not modifying_entries:
            return data

        self._emitting.add(event)
        try:
            current = data
            for entry in modifying_entries:
                result = await asyncio.wait_for(
                    entry.handler(event, current),
                    timeout=self._handler_timeout,
                )
                if result is not None:
                    current = result
            return current
        finally:
            self._emitting.discard(event)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all registered handlers and reset frozen state."""
        self._handlers = {event: [] for event in HookEvent}
        self._frozen = False
        self._emitting = set()

    def freeze(self) -> None:
        """Prevent any further handler registration."""
        self._frozen = True

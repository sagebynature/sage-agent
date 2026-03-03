"""OpenTelemetry tracing support for Sage.

Provides a ``span()`` async context manager that creates real OTel spans when
the ``opentelemetry-api`` package is installed, or a zero-cost no-op when it
is not.  All instrumentation in the rest of the codebase calls ``span()``
unconditionally — no ``if tracing_enabled`` guards needed.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

_TRACER_NAME = "sage-agent"

# ---------------------------------------------------------------------------
# No-op fallback (used when opentelemetry-api is not installed)
# ---------------------------------------------------------------------------


class _NoOpSpan:
    """Minimal stand-in for opentelemetry.trace.Span."""

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: ARG002
        pass

    def record_exception(self, exc: BaseException) -> None:  # noqa: ARG002
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@asynccontextmanager
async def span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> AsyncIterator[Any]:
    """Async context manager that wraps a block in an OTel span.

    When ``opentelemetry-api`` is not installed, yields a no-op span object
    so callers never need to check whether tracing is available.

    Usage::

        async with span("agent.run", {"agent.name": self.name}) as s:
            s.set_attribute("turn_count", turns)
            result = await do_work()

    Args:
        name: Span name (e.g. ``"agent.run"``, ``"tool.execute"``).
        attributes: Initial span attributes as a flat dict.

    Yields:
        Either a real ``opentelemetry.trace.Span`` or a ``_NoOpSpan``.
    """
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]

        tracer = trace.get_tracer(_TRACER_NAME)
        with tracer.start_as_current_span(name, attributes=attributes or {}) as real_span:
            try:
                yield real_span
            except Exception as exc:
                from opentelemetry.trace import StatusCode  # type: ignore[import-not-found]

                real_span.record_exception(exc)
                real_span.set_status(StatusCode.ERROR, str(exc))
                raise
    except ImportError:
        yield _NoOpSpan()


def setup_tracing(config: Any) -> None:
    """Configure the OTel SDK from ``TracingConfig``.

    Called once at agent startup when ``tracing:`` is set in the agent
    frontmatter.  When OTel is not installed this is a silent no-op.

    Args:
        config: A ``TracingConfig`` instance.
    """
    if config is None or not config.enabled:
        return

    try:
        from opentelemetry import trace  # noqa: PLC0415  # type: ignore[import-not-found]
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace.export import (  # type: ignore[import-not-found]
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except ImportError:
        logger.debug("opentelemetry-sdk not installed; tracing disabled")
        return

    resource = Resource.create({"service.name": config.service_name})
    provider = TracerProvider(resource=resource)

    if config.exporter == "console":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    elif config.exporter == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import-not-found]
                OTLPSpanExporter,
            )

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        except ImportError:
            logger.warning("opentelemetry-exporter-otlp not installed; OTLP export disabled")

    trace.set_tracer_provider(provider)
    logger.info("Tracing enabled: service=%s, exporter=%s", config.service_name, config.exporter)

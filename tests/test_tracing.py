"""Tests for sage/tracing.py — no-op and real-span paths."""

from __future__ import annotations

import pytest


class TestNoOpSpan:
    def test_noop_span_methods_dont_raise(self) -> None:
        from sage.tracing import _NoOpSpan

        s = _NoOpSpan()
        s.set_attribute("k", "v")
        s.record_exception(ValueError("x"))
        s.set_status()

    @pytest.mark.asyncio
    async def test_span_context_manager_always_works(self) -> None:
        """span() runs without errors regardless of OTel availability."""
        from sage.tracing import span as sage_span

        async with sage_span("test.always") as s:
            s.set_attribute("ok", True)
        # No assertion needed — if it ran without raising, it works.

    @pytest.mark.asyncio
    async def test_span_propagates_exceptions(self) -> None:
        """Exceptions inside span() must always propagate."""
        from sage.tracing import span as sage_span

        with pytest.raises(RuntimeError, match="from inside span"):
            async with sage_span("test.exc"):
                raise RuntimeError("from inside span")


class TestTracingConfig:
    """TracingConfig validation and defaults."""

    def test_default_values(self) -> None:
        from sage.config import TracingConfig

        cfg = TracingConfig()
        assert cfg.enabled is False
        assert cfg.service_name == "sage-agent"
        assert cfg.exporter == "none"

    def test_custom_values(self) -> None:
        from sage.config import TracingConfig

        cfg = TracingConfig(enabled=True, service_name="my-service", exporter="console")
        assert cfg.enabled is True
        assert cfg.service_name == "my-service"
        assert cfg.exporter == "console"

    def test_invalid_exporter_raises(self) -> None:
        from pydantic import ValidationError

        from sage.config import TracingConfig

        with pytest.raises(ValidationError):
            TracingConfig(exporter="invalid")  # type: ignore[arg-type]

    def test_agent_config_tracing_field(self) -> None:
        """AgentConfig.tracing defaults to None."""
        from sage.config import AgentConfig

        cfg = AgentConfig(name="test", model="gpt-4o")
        assert cfg.tracing is None

    def test_agent_config_tracing_inline(self) -> None:
        """AgentConfig accepts inline TracingConfig."""
        from sage.config import AgentConfig, TracingConfig

        cfg = AgentConfig(
            name="test",
            model="gpt-4o",
            tracing=TracingConfig(enabled=True, exporter="console"),
        )
        assert cfg.tracing is not None
        assert cfg.tracing.enabled is True


class TestSetupTracing:
    """setup_tracing() behaviour."""

    def test_setup_tracing_none_is_noop(self) -> None:
        """setup_tracing(None) must not raise."""
        from sage.tracing import setup_tracing

        setup_tracing(None)  # should not raise

    def test_setup_tracing_disabled_is_noop(self) -> None:
        """setup_tracing with enabled=False must not raise or configure anything."""
        from sage.config import TracingConfig
        from sage.tracing import setup_tracing

        setup_tracing(TracingConfig(enabled=False))  # should not raise

    def test_setup_tracing_console_when_otel_available(self) -> None:
        """setup_tracing with console exporter configures a TracerProvider (if OTel installed)."""
        pytest.importorskip("opentelemetry.sdk.trace")
        from opentelemetry import trace

        from sage.config import TracingConfig
        from sage.tracing import setup_tracing

        cfg = TracingConfig(enabled=True, service_name="test-svc", exporter="console")
        setup_tracing(cfg)

        provider = trace.get_tracer_provider()
        assert provider is not None


class TestSpanWithOTel:
    """Real span creation when opentelemetry-sdk is installed (skip if absent)."""

    @pytest.mark.asyncio
    async def test_real_span_created_when_otel_installed(self) -> None:
        """span() creates a real span captured by InMemorySpanExporter."""
        pytest.importorskip("opentelemetry.sdk.trace")
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        from sage.tracing import span as sage_span

        async with sage_span("test.span", {"key": "value"}):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) >= 1
        span_names = [s.name for s in spans]
        assert "test.span" in span_names

    @pytest.mark.asyncio
    async def test_span_records_exception(self) -> None:
        """Exceptions inside span() are recorded on the span and re-raised."""
        pytest.importorskip("opentelemetry.sdk.trace")
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        from opentelemetry.trace import StatusCode

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        from sage.tracing import span as sage_span

        with pytest.raises(ValueError, match="oops"):
            async with sage_span("test.error"):
                raise ValueError("oops")

        spans = exporter.get_finished_spans()
        error_spans = [s for s in spans if s.name == "test.error"]
        assert len(error_spans) == 1
        assert error_spans[0].status.status_code == StatusCode.ERROR

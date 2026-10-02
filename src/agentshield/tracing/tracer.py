"""Spans around a run. The core install stores the trace without a SDK.

Span attributes are the event kind, tool name, argument hash, duration, and
token count. Raw arguments and canary strings are not attributes.
"""

from collections.abc import Mapping
from typing import Any, Protocol

AttributeValue = str | int | float


class Span(Protocol):
    """One open span. `end` finishes it."""

    def set_attributes(self, attributes: Mapping[str, AttributeValue]) -> None:
        """Attach the allowed attributes. Values are strings, ints, or floats."""

    def end(self) -> None:
        """Finish the span."""


class Tracer(Protocol):
    """Starts spans. The default implementation records nothing."""

    def start_span(self, name: str) -> Span:
        """Open a span with this name."""


class NullSpan:
    """A span that keeps no attributes."""

    def set_attributes(self, attributes: Mapping[str, AttributeValue]) -> None:
        del attributes

    def end(self) -> None:
        return None


class NullTracer:
    """Used when the caller does not pass an OpenTelemetry tracer."""

    def start_span(self, name: str) -> NullSpan:
        del name
        return NullSpan()


class _SdkSpan:
    def __init__(self, span: Any) -> None:
        self._span = span

    def set_attributes(self, attributes: Mapping[str, AttributeValue]) -> None:
        for key, value in attributes.items():
            self._span.set_attribute(key, value)

    def end(self) -> None:
        self._span.end()


class _SdkTracer:
    def __init__(self, tracer: Any) -> None:
        self._tracer = tracer

    def start_span(self, name: str) -> _SdkSpan:
        return _SdkSpan(self._tracer.start_span(name))


def otel_run_tracer(provider: object) -> Tracer:
    """Wrap an OpenTelemetry `TracerProvider`. Requires the `otel` extra."""
    try:
        from opentelemetry.sdk.trace import TracerProvider
    except ImportError as exc:
        raise ImportError("spans require the agentshield[otel] extra") from exc
    if not isinstance(provider, TracerProvider):
        raise TypeError("provider must be an OpenTelemetry TracerProvider")
    return _SdkTracer(provider.get_tracer("agentshield"))


def configure_otlp_tracer(endpoint: str = "http://localhost:4318/v1/traces") -> Tracer:
    """Export spans over OTLP/HTTP. Requires the `otel` extra.

    The default endpoint is Jaeger on the compose `debug` profile. This does
    not start a collector.
    """
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        raise ImportError("OTLP export requires the agentshield[otel] extra") from exc
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    return _SdkTracer(provider.get_tracer("agentshield"))

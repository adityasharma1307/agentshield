"""Optional tracing. The recorded `AgentTrace` does not require this package."""

from agentshield.tracing.tracer import (
    NullTracer,
    Span,
    Tracer,
    configure_otlp_tracer,
    otel_run_tracer,
)

__all__ = [
    "NullTracer",
    "Span",
    "Tracer",
    "configure_otlp_tracer",
    "otel_run_tracer",
]

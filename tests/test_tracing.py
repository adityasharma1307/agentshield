"""Span tests. They use an in-memory exporter and do not start a collector."""

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from agentshield.adapters.base import AgentUnderTest
from agentshield.sandbox.executor import run_agent
from agentshield.sandbox.tools import MockTool, ToolRegistry
from agentshield.trace import AgentStep, ToolCall, ToolSpec, TraceEvent
from agentshield.tracing.tracer import otel_run_tracer

_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}
_ALLOWED_ATTRIBUTES = {"event.kind", "tool.name", "args_sha256", "duration_ms", "token_count"}


class _TwoCalls(AgentUnderTest):
    def __init__(self) -> None:
        self._calls = 0

    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        del task, tools, history, context
        self._calls += 1
        if self._calls == 1:
            return AgentStep(
                kind="tool_calls",
                token_count=4,
                calls=[
                    ToolCall(name="echo", arguments={"text": "one"}),
                    ToolCall(name="echo", arguments={"text": "CANARY-abc"}),
                ],
            )
        return AgentStep(kind="final", text="done", token_count=9)


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        MockTool(
            name="echo",
            description="Echo.",
            parameters=_SCHEMA,
            handler=lambda arguments, scenario_state: f"echo: {arguments['text']}",
        )
    )
    return registry


async def test_two_tool_calls_emit_spans_in_event_order() -> None:
    pytest.importorskip("opentelemetry.sdk.trace")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    try:
        outcome = await run_agent(
            _TwoCalls(),
            "task",
            _registry(),
            tracer=otel_run_tracer(provider),
        )
    finally:
        provider.shutdown()

    events = outcome.trace.events
    spans = exporter.get_finished_spans()
    assert [event.kind for event in events] == [
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "final",
    ]
    attribute_maps: list[Mapping[str, Any]] = []
    for span in spans:
        assert span.attributes is not None
        attribute_maps.append(span.attributes)
    assert [attributes["event.kind"] for attributes in attribute_maps] == [
        event.kind for event in events
    ]
    assert [span.name for span in spans] == [
        "tool.dispatch",
        "tool.dispatch",
        "tool.dispatch",
        "tool.dispatch",
        "agent.step",
    ]
    for event, attributes in zip(events, attribute_maps, strict=True):
        assert set(attributes) <= _ALLOWED_ATTRIBUTES
        if event.args_sha256 is not None:
            assert attributes["args_sha256"] == event.args_sha256
        if event.name is not None:
            assert attributes["tool.name"] == event.name
        if event.token_count is not None:
            assert attributes["token_count"] == event.token_count
        for value in attributes.values():
            assert "CANARY-abc" not in str(value)
            assert "one" not in str(value)
    assert events[0].arguments == {"text": "one"}
    assert events[2].arguments == {"text": "CANARY-abc"}
    assert events[3].output == "echo: CANARY-abc"

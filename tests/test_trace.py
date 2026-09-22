"""Tests for trace and step models."""

import pytest
from pydantic import ValidationError

from agentshield.trace import AgentStep, AgentTrace, ToolCall, ToolSpec, TraceEvent


def test_sequence_must_start_at_zero_and_increase_by_one() -> None:
    with pytest.raises(ValidationError):
        AgentTrace(events=[TraceEvent(sequence=1, kind="final")], final_text="x")
    with pytest.raises(ValidationError):
        AgentTrace(
            events=[
                TraceEvent(sequence=0, kind="tool_call", name="search"),
                TraceEvent(sequence=2, kind="final"),
            ],
            final_text="x",
        )


def test_contiguous_sequence_is_accepted() -> None:
    trace = AgentTrace(
        events=[
            TraceEvent(sequence=0, kind="tool_call", name="search", arguments={"q": "a"}),
            TraceEvent(sequence=1, kind="final", text="done"),
        ],
        final_text="done",
    )
    assert [event.sequence for event in trace.events] == [0, 1]


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ToolSpec.model_validate(
            {"name": "search", "description": "look up", "parameters": {}, "extra": True}
        )


def test_final_step_has_no_calls() -> None:
    with pytest.raises(ValidationError):
        AgentStep(kind="final", calls=[ToolCall(name="search", arguments={})], text="no")


def test_tool_calls_step_has_at_least_one_call() -> None:
    with pytest.raises(ValidationError):
        AgentStep(kind="tool_calls", calls=[])


def test_final_step_defaults_to_no_calls() -> None:
    step = AgentStep(kind="final", text="done")
    assert step.calls == []
    assert step.text == "done"

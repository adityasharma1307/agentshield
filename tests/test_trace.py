"""Tests for trace and step models."""

import hashlib
import json

import pytest
from pydantic import ValidationError

from agentshield.trace import (
    AgentStep,
    AgentTrace,
    ToolCall,
    ToolSpec,
    TraceEvent,
    arguments_sha256,
)


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


def test_optional_trace_fields_default_to_empty() -> None:
    event = TraceEvent(sequence=0, kind="final")
    assert event.started_ns is None
    assert event.duration_ms is None
    assert event.token_count is None
    assert event.args_sha256 is None


def test_arguments_sha256_uses_sorted_compact_json() -> None:
    first = arguments_sha256({"b": 1, "a": "x"})
    second = arguments_sha256({"a": "x", "b": 1})
    encoded = json.dumps({"a": "x", "b": 1}, sort_keys=True, separators=(",", ":")).encode()
    assert first == second
    assert first == hashlib.sha256(encoded).hexdigest()
    assert " " not in json.dumps({"a": "x", "b": 1}, sort_keys=True, separators=(",", ":"))

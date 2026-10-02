"""Normalized trace and step models shared by adapters and later phases.

The sandbox, not the adapter, executes tools. An adapter returns an `AgentStep`.
The executor records `TraceEvent` values. Optional timing and `args_sha256`
describe a call. The full arguments stay on the event.
"""

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolSpec(BaseModel):
    """A tool the agent is allowed to ask for. This is a schema, not a handler."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parameters: dict[str, Any]


class ToolCall(BaseModel):
    """One tool invocation requested by the agent. Nothing has run it yet."""

    model_config = ConfigDict(extra="forbid")

    name: str
    arguments: dict[str, Any]


class TraceEvent(BaseModel):
    """One recorded moment in a run."""

    model_config = ConfigDict(extra="forbid")

    sequence: int
    kind: Literal["llm_call", "tool_call", "tool_result", "final"]
    name: str | None = None
    text: str | None = None
    arguments: dict[str, Any] | None = None
    output: str | None = None
    started_ns: int | None = None
    duration_ms: float | None = None
    token_count: int | None = None
    args_sha256: str | None = None


class AgentTrace(BaseModel):
    """The ordered record of a finished or stopped run."""

    model_config = ConfigDict(extra="forbid")

    events: list[TraceEvent]
    final_text: str

    @model_validator(mode="after")
    def _sequences_are_contiguous(self) -> Self:
        for position, event in enumerate(self.events):
            if event.sequence != position:
                raise ValueError(
                    "event sequence must be 0, 1, 2, ...; "
                    f"found {event.sequence} at position {position}"
                )
        return self


class AgentStep(BaseModel):
    """The next action an adapter returns. Tool calls are requests, not results."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["tool_calls", "final"]
    calls: list[ToolCall] = Field(default_factory=list)
    text: str = ""
    token_count: int | None = None

    @model_validator(mode="after")
    def _shape_matches_kind(self) -> Self:
        if self.kind == "final" and self.calls:
            raise ValueError("a final step has no tool calls")
        if self.kind == "tool_calls" and not self.calls:
            raise ValueError("a tool_calls step has at least one call")
        return self


def arguments_sha256(arguments: Mapping[str, Any]) -> str:
    """Hex sha256 of canonical JSON: sorted keys, compact separators."""
    encoded = json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

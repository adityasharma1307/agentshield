"""The step loop. This is the only code that calls `ToolRegistry.dispatch`.

`step()` never sees the registry. It gets `tools`, `history`, and `context`
and returns the next action; the executor is what turns a requested call into
a recorded result.

The executor keeps the event list private. `step()` gets a tuple of deep
copies, and a requested call's arguments are deep-copied before they are
recorded, so nothing the agent holds aliases the trace that gets scored.
Before a run is returned, the outbound record the tool handlers kept in
`scenario_state["outbound"]` is checked against the trace; a mismatch raises
`TraceIntegrityError` instead of returning a trace that might be clean.
"""

import copy
from collections.abc import Callable, Mapping
from time import monotonic, time_ns
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from agentshield.adapters.base import AgentUnderTest
from agentshield.config import Settings
from agentshield.sandbox.tools import (
    ScenarioState,
    ToolArgumentError,
    ToolRegistry,
    UnknownToolError,
)
from agentshield.trace import AgentTrace, ToolCall, TraceEvent, arguments_sha256
from agentshield.tracing.tracer import NullTracer, Tracer

StoppedReason = Literal["completed", "max_steps", "time_limit", "agent_error"]


class TraceIntegrityError(RuntimeError):
    """The trace does not account for every outbound call a handler recorded."""


class RunOutcome(BaseModel):
    """A finished or stopped run: the trace collected, and why it stopped."""

    model_config = ConfigDict(extra="forbid")

    trace: AgentTrace
    stopped_reason: StoppedReason


async def run_agent(
    agent: AgentUnderTest,
    task: str,
    registry: ToolRegistry,
    *,
    scenario_state: ScenarioState | None = None,
    context: Mapping[str, str] | None = None,
    settings: Settings | None = None,
    clock: Callable[[], float] = monotonic,
    now_ns: Callable[[], int] = time_ns,
    tracer: Tracer | None = None,
) -> RunOutcome:
    """Run `agent` against `task`, dispatching its tool calls through `registry`.

    Stops on a final step, on `settings.max_steps` calls to `step()`, on
    `settings.time_limit_s` elapsed by `clock`, or on an exception from `step()`.
    Every event recorded before a stop is kept. `now_ns` stamps those events.
    `tracer` receives one span per event; the default tracer records nothing.
    """
    settings = settings or Settings()
    scenario_state = scenario_state if scenario_state is not None else {}
    context = context if context is not None else {}
    tracer = tracer if tracer is not None else NullTracer()
    tools = registry.specs()

    events: list[TraceEvent] = []
    start = clock()
    steps_taken = 0

    while True:
        if clock() - start >= settings.time_limit_s:
            return _stopped(events, "time_limit", tracer, scenario_state)
        if steps_taken >= settings.max_steps:
            return _stopped(events, "max_steps", tracer, scenario_state)

        steps_taken += 1
        started = now_ns()
        try:
            step = await agent.step(task, tools, _snapshot(events), dict(context))
        except Exception:
            return _stopped(events, "agent_error", tracer, scenario_state)
        duration_ms = (now_ns() - started) / 1_000_000

        if step.kind == "final":
            _append(
                events,
                tracer,
                kind="final",
                text=step.text,
                started_ns=started,
                duration_ms=duration_ms,
                token_count=step.token_count,
            )
            return _finish(events, step.text, "completed", scenario_state)

        for requested in step.calls:
            call = ToolCall(name=requested.name, arguments=copy.deepcopy(requested.arguments))
            _append(
                events,
                tracer,
                kind="tool_call",
                name=call.name,
                arguments=call.arguments,
                started_ns=started,
                duration_ms=duration_ms,
                token_count=step.token_count,
            )
            dispatch_started = now_ns()
            try:
                output = registry.dispatch(call, scenario_state)
            except (UnknownToolError, ToolArgumentError) as exc:
                output = f"error: {exc}"
            dispatch_ms = (now_ns() - dispatch_started) / 1_000_000
            _append(
                events,
                tracer,
                kind="tool_result",
                name=call.name,
                output=output,
                started_ns=dispatch_started,
                duration_ms=dispatch_ms,
            )


def _append(
    events: list[TraceEvent],
    tracer: Tracer,
    *,
    kind: Literal["tool_call", "tool_result", "final"],
    name: str | None = None,
    text: str | None = None,
    arguments: dict[str, Any] | None = None,
    output: str | None = None,
    started_ns: int | None = None,
    duration_ms: float | None = None,
    token_count: int | None = None,
) -> None:
    event = TraceEvent(
        sequence=len(events),
        kind=kind,
        name=name,
        text=text,
        arguments=arguments,
        output=output,
        started_ns=started_ns,
        duration_ms=duration_ms,
        token_count=token_count,
        args_sha256=arguments_sha256(arguments) if arguments is not None else None,
    )
    events.append(event)
    _emit(tracer, event)


def _emit(tracer: Tracer, event: TraceEvent) -> None:
    span_name = "agent.step" if event.kind == "final" else "tool.dispatch"
    attributes: dict[str, str | int | float] = {"event.kind": event.kind}
    if event.name is not None:
        attributes["tool.name"] = event.name
    if event.args_sha256 is not None:
        attributes["args_sha256"] = event.args_sha256
    if event.duration_ms is not None:
        attributes["duration_ms"] = event.duration_ms
    if event.token_count is not None:
        attributes["token_count"] = event.token_count
    span = tracer.start_span(span_name)
    span.set_attributes(attributes)
    span.end()


def _snapshot(events: list[TraceEvent]) -> tuple[TraceEvent, ...]:
    """What `step()` sees: copies, so mutating them cannot reach the recorded trace."""
    return tuple(event.model_copy(deep=True) for event in events)


def _stopped(
    events: list[TraceEvent],
    reason: StoppedReason,
    tracer: Tracer,
    scenario_state: ScenarioState,
) -> RunOutcome:
    _append(events, tracer, kind="final", text="")
    return _finish(events, "", reason, scenario_state)


def _finish(
    events: list[TraceEvent],
    final_text: str,
    reason: StoppedReason,
    scenario_state: ScenarioState,
) -> RunOutcome:
    trace = AgentTrace(
        events=[event.model_copy(deep=True) for event in events], final_text=final_text
    )
    check_outbound(trace, scenario_state)
    return RunOutcome(trace=trace, stopped_reason=reason)


def check_outbound(trace: AgentTrace, scenario_state: ScenarioState) -> None:
    """Raise `TraceIntegrityError` unless every outbound record is a traced call.

    Handlers append `{"tool", "arguments"}` to `scenario_state["outbound"]` for
    each outbound call they run. Each record must match, in order, a
    `tool_call` event with the same name and arguments.
    """
    records = scenario_state.get("outbound", [])
    if not isinstance(records, list):
        raise TraceIntegrityError("scenario_state['outbound'] is not a list")
    calls = iter(event for event in trace.events if event.kind == "tool_call")
    for index, record in enumerate(records):
        tool = record.get("tool") if isinstance(record, dict) else None
        arguments = record.get("arguments") if isinstance(record, dict) else None
        if not any(event.name == tool and event.arguments == arguments for event in calls):
            raise TraceIntegrityError(
                f"outbound record {index} ({tool}) has no matching tool_call in the trace"
            )

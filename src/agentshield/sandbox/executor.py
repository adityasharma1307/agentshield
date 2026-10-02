"""The step loop. This is the only code that calls `ToolRegistry.dispatch`.

`step()` never sees the registry. It gets `tools`, `history`, and `context`
and returns the next action; the executor is what turns a requested call into
a recorded result.
"""

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
from agentshield.trace import AgentTrace, TraceEvent, arguments_sha256
from agentshield.tracing.tracer import NullTracer, Tracer

StoppedReason = Literal["completed", "max_steps", "time_limit", "agent_error"]


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
            return _stopped(events, "time_limit", tracer)
        if steps_taken >= settings.max_steps:
            return _stopped(events, "max_steps", tracer)

        steps_taken += 1
        started = now_ns()
        try:
            step = await agent.step(task, tools, events, context)
        except Exception:
            return _stopped(events, "agent_error", tracer)
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
            return RunOutcome(
                trace=AgentTrace(events=events, final_text=step.text),
                stopped_reason="completed",
            )

        for call in step.calls:
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


def _stopped(events: list[TraceEvent], reason: StoppedReason, tracer: Tracer) -> RunOutcome:
    _append(events, tracer, kind="final", text="")
    return RunOutcome(trace=AgentTrace(events=events, final_text=""), stopped_reason=reason)

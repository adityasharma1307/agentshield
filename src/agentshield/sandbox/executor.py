"""The step loop. This is the only code that calls `ToolRegistry.dispatch`.

`step()` never sees the registry. It gets `tools`, `history`, and `context`
and returns the next action; the executor is what turns a requested call into
a recorded result.
"""

from collections.abc import Callable, Mapping
from time import monotonic
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
from agentshield.trace import AgentTrace, TraceEvent

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
) -> RunOutcome:
    """Run `agent` against `task`, dispatching its tool calls through `registry`.

    Stops on a final step, on `settings.max_steps` calls to `step()`, on
    `settings.time_limit_s` elapsed by `clock`, or on an exception from `step()`.
    Every event recorded before a stop is kept.
    """
    settings = settings or Settings()
    scenario_state = scenario_state if scenario_state is not None else {}
    context = context if context is not None else {}
    tools = registry.specs()

    events: list[TraceEvent] = []
    start = clock()
    steps_taken = 0

    while True:
        if clock() - start >= settings.time_limit_s:
            return _stopped(events, "time_limit")
        if steps_taken >= settings.max_steps:
            return _stopped(events, "max_steps")

        steps_taken += 1
        try:
            step = await agent.step(task, tools, events, context)
        except Exception:
            return _stopped(events, "agent_error")

        if step.kind == "final":
            _append(events, kind="final", text=step.text)
            return RunOutcome(
                trace=AgentTrace(events=events, final_text=step.text),
                stopped_reason="completed",
            )

        for call in step.calls:
            _append(events, kind="tool_call", name=call.name, arguments=call.arguments)
            try:
                output = registry.dispatch(call, scenario_state)
            except (UnknownToolError, ToolArgumentError) as exc:
                output = f"error: {exc}"
            _append(events, kind="tool_result", name=call.name, output=output)


def _append(
    events: list[TraceEvent],
    *,
    kind: Literal["tool_call", "tool_result", "final"],
    name: str | None = None,
    text: str | None = None,
    arguments: dict[str, Any] | None = None,
    output: str | None = None,
) -> None:
    events.append(
        TraceEvent(
            sequence=len(events),
            kind=kind,
            name=name,
            text=text,
            arguments=arguments,
            output=output,
        )
    )


def _stopped(events: list[TraceEvent], reason: StoppedReason) -> RunOutcome:
    closed = [*events, TraceEvent(sequence=len(events), kind="final", text="")]
    return RunOutcome(trace=AgentTrace(events=closed, final_text=""), stopped_reason=reason)

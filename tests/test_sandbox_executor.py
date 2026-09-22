"""Tests for the executor loop, driven by a fake `AgentUnderTest`."""

from collections.abc import Iterator, Mapping, Sequence

from agentshield.adapters.base import AgentUnderTest
from agentshield.config import Settings
from agentshield.sandbox.executor import run_agent
from agentshield.sandbox.tools import MockTool, ToolRegistry
from agentshield.trace import AgentStep, ToolCall, ToolSpec, TraceEvent

_ECHO_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        MockTool(
            name="echo",
            description="Echo the text argument back.",
            parameters=_ECHO_SCHEMA,
            handler=lambda arguments, scenario_state: f"echo: {arguments['text']}",
        )
    )
    return registry


class ScriptedAgent(AgentUnderTest):
    """Returns each of `steps` in order; repeats the last step once exhausted."""

    def __init__(self, steps: Sequence[AgentStep]) -> None:
        self._steps = list(steps)
        self.calls = 0

    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        del task, tools, history, context
        step = self._steps[min(self.calls, len(self._steps) - 1)]
        self.calls += 1
        return step


class ExplodingAgent(AgentUnderTest):
    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        del task, tools, history, context
        raise RuntimeError("the target agent crashed")


def _fake_clock(values: Sequence[float]) -> Iterator[float]:
    yield from values


async def test_tool_call_then_final() -> None:
    agent = ScriptedAgent(
        [
            AgentStep(kind="tool_calls", calls=[ToolCall(name="echo", arguments={"text": "hi"})]),
            AgentStep(kind="final", text="done"),
        ]
    )
    outcome = await run_agent(agent, "task", _registry())
    assert outcome.stopped_reason == "completed"
    assert outcome.trace.final_text == "done"
    kinds = [event.kind for event in outcome.trace.events]
    assert kinds == ["tool_call", "tool_result", "final"]
    assert outcome.trace.events[1].output == "echo: hi"


async def test_unknown_tool_becomes_an_error_result_and_the_run_continues() -> None:
    agent = ScriptedAgent(
        [
            AgentStep(kind="tool_calls", calls=[ToolCall(name="missing", arguments={})]),
            AgentStep(kind="final", text="gave up"),
        ]
    )
    outcome = await run_agent(agent, "task", _registry())
    assert outcome.stopped_reason == "completed"
    tool_result = outcome.trace.events[1]
    assert tool_result.kind == "tool_result"
    assert tool_result.output is not None
    assert tool_result.output.startswith("error:")
    assert "missing" in tool_result.output
    assert outcome.trace.final_text == "gave up"


async def test_max_steps_stops_the_run_and_keeps_recorded_events() -> None:
    agent = ScriptedAgent(
        [AgentStep(kind="tool_calls", calls=[ToolCall(name="echo", arguments={"text": "x"})])]
    )
    outcome = await run_agent(
        agent, "task", _registry(), settings=Settings(max_steps=2, time_limit_s=60)
    )
    assert outcome.stopped_reason == "max_steps"
    assert agent.calls == 2
    kinds = [event.kind for event in outcome.trace.events]
    assert kinds == ["tool_call", "tool_result", "tool_call", "tool_result", "final"]
    assert outcome.trace.events[-1].text == ""
    assert outcome.trace.final_text == ""


async def test_time_limit_stops_the_run_without_sleeping() -> None:
    agent = ScriptedAgent(
        [AgentStep(kind="tool_calls", calls=[ToolCall(name="echo", arguments={"text": "x"})])]
    )
    clock = _fake_clock([0.0, 5.0, 40.0])
    outcome = await run_agent(
        agent,
        "task",
        _registry(),
        settings=Settings(max_steps=8, time_limit_s=30),
        clock=lambda: next(clock),
    )
    assert outcome.stopped_reason == "time_limit"
    kinds = [event.kind for event in outcome.trace.events]
    assert kinds == ["tool_call", "tool_result", "final"]
    assert outcome.trace.events[-1].text == ""


async def test_agent_exception_stops_the_run_as_agent_error() -> None:
    outcome = await run_agent(ExplodingAgent(), "task", _registry())
    assert outcome.stopped_reason == "agent_error"
    assert outcome.trace.events == [TraceEvent(sequence=0, kind="final", text="")]


async def test_scenario_state_flows_from_tool_calls_to_handlers() -> None:
    def note_handler(arguments: dict[str, object], scenario_state: dict[str, object]) -> str:
        notes = scenario_state.setdefault("notes", [])
        assert isinstance(notes, list)
        notes.append(arguments["text"])
        return "ok"

    registry = ToolRegistry()
    registry.register(
        MockTool(
            name="note",
            description="records a note",
            parameters=_ECHO_SCHEMA,
            handler=note_handler,
        )
    )
    agent = ScriptedAgent(
        [
            AgentStep(kind="tool_calls", calls=[ToolCall(name="note", arguments={"text": "a"})]),
            AgentStep(kind="final", text="done"),
        ]
    )
    scenario_state: dict[str, object] = {}
    await run_agent(agent, "task", registry, scenario_state=scenario_state)
    assert scenario_state["notes"] == ["a"]

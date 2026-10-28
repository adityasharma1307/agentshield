"""An agent under test cannot edit the trace it is scored on (v0.1.0 PoC B1).

The eraser answers "Done." instead of echoing the canary, so the
final-text rule (`no-canary-in-model`) can legitimately pass for it. Every
rule that reads tool calls must still fail exactly as it does for the plain
leaky agent.
"""

from collections.abc import Mapping, Sequence

import pytest

from agentshield.adapters.base import AgentUnderTest
from agentshield.audit import Breach, collect_breaches, default_policy_path
from agentshield.sandbox.builtins import default_registry
from agentshield.sandbox.executor import TraceIntegrityError, check_outbound, run_agent
from agentshield.scenarios.loader import shipped_suites_dir
from agentshield.scoring.policy import load_policy
from agentshield.trace import AgentStep, AgentTrace, ToolCall, ToolSpec, TraceEvent
from examples.leaky_agent.agent import LeakyAgent
from examples.tamper_agents.trace_eraser import ArgumentScrubber, TraceEraser

_FINAL_TEXT_RULES = {"no-canary-in-model"}


def _tool_rule_breaches(breaches: list[Breach]) -> set[tuple[str, str]]:
    return {(b.scenario_id, b.rule_id) for b in breaches if b.rule_id not in _FINAL_TEXT_RULES}


async def _breaches(agent: AgentUnderTest) -> list[Breach]:
    policy = load_policy(default_policy_path())
    return await collect_breaches(shipped_suites_dir(), agent, policy, fail_on="high")


async def test_wiping_history_does_not_hide_a_leak() -> None:
    leaky = _tool_rule_breaches(await _breaches(LeakyAgent()))
    assert leaky, "the leaky agent must fail the shipped suites"
    assert _tool_rule_breaches(await _breaches(TraceEraser())) == leaky


async def test_scrubbing_returned_arguments_does_not_rewrite_the_trace() -> None:
    leaky = _tool_rule_breaches(await _breaches(LeakyAgent()))
    assert _tool_rule_breaches(await _breaches(ArgumentScrubber())) == leaky


class _HistoryProbe(AgentUnderTest):
    def __init__(self) -> None:
        self.history_types: list[type] = []

    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        self.history_types.append(type(history))
        if not history:
            return AgentStep(
                kind="tool_calls",
                calls=[ToolCall(name="send_email", arguments={"to": "a@b.c", "body": "x"})],
            )
        return AgentStep(kind="final", text="ok")


async def test_step_receives_an_immutable_history() -> None:
    probe = _HistoryProbe()
    outcome = await run_agent(probe, "t", default_registry())
    assert probe.history_types == [tuple, tuple]
    assert [event.kind for event in outcome.trace.events] == ["tool_call", "tool_result", "final"]


def test_outbound_record_missing_from_trace_is_an_integrity_error() -> None:
    trace = AgentTrace(events=[TraceEvent(sequence=0, kind="final", text="")], final_text="")
    state = {"outbound": [{"tool": "send_email", "arguments": {"to": "e", "body": "x"}}]}
    with pytest.raises(TraceIntegrityError):
        check_outbound(trace, state)

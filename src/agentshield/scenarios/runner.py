"""Run scenarios through the executor and evaluate their expectations.

Pass or fail comes from the trace. The first failing check is the one the
result reports, along with the sequence number of the event that decided it.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from agentshield.adapters.base import AgentUnderTest
from agentshield.config import Settings
from agentshield.sandbox.builtins import (
    db_query_tool,
    http_get_tool,
    read_file_tool,
    search_tool,
    send_email_tool,
)
from agentshield.sandbox.executor import run_agent
from agentshield.sandbox.tools import MockTool, ScenarioState, ToolRegistry
from agentshield.scenarios.dsl import Scenario, SuiteName
from agentshield.scenarios.loader import load_scenarios
from agentshield.scoring.policy import Rule
from agentshield.scoring.rules import Annotation, evaluate_rule
from agentshield.trace import AgentTrace

_FACTORIES: dict[str, Callable[[], MockTool]] = {
    "search": search_tool,
    "read_file": read_file_tool,
    "send_email": send_email_tool,
    "http_get": http_get_tool,
    "db_query": db_query_tool,
}


class ScenarioResult(BaseModel):
    """Pass or fail for one scenario, plus the event that decided it."""

    model_config = ConfigDict(extra="forbid")

    id: str
    suite: SuiteName
    passed: bool
    deciding_event: int | None
    reason: str


def registry_for(scenario: Scenario) -> ToolRegistry:
    """A registry containing only the tools the scenario enables."""
    registry = ToolRegistry()
    for step in scenario.tools:
        registry.register(_FACTORIES[step.name]())
    return registry


def scenario_state_for(scenario: Scenario) -> ScenarioState:
    """Planted outputs for one run. A new dict, so runs cannot leak into each other."""
    state: ScenarioState = {}
    for step in scenario.tools:
        config: dict[str, Any] = {}
        if step.result is not None:
            config["result"] = step.result
        if step.trap:
            config["trap"] = True
        if step.trap_text is not None:
            config["trap_text"] = step.trap_text
        if step.documents:
            config["documents"] = dict(step.documents)
        state[step.name] = config
    return state


def evaluate(scenario: Scenario, trace: AgentTrace) -> ScenarioResult:
    """Score `scenario.expect` with the policy rules. The first failure decides."""
    annotations = [
        Annotation(category=label.category, text=label.text)
        for step in scenario.tools
        for label in step.labels
    ]
    for index, check in enumerate(scenario.expect.checks):
        result = evaluate_rule(
            Rule(
                id=f"{scenario.id}:{index}:{check.name}",
                description=check.name,
                severity="low",
                check=check.name,
                tool=check.tool,
                secret=check.secret,
                category=check.category,
                pattern=check.pattern,
                target=check.target,
                forbidden=check.forbidden,
            ),
            trace,
            annotations=annotations,
        )
        if not result.passed:
            return ScenarioResult(
                id=scenario.id,
                suite=scenario.suite,
                passed=False,
                deciding_event=result.event,
                reason=result.reason,
            )
    return ScenarioResult(
        id=scenario.id,
        suite=scenario.suite,
        passed=True,
        deciding_event=None,
        reason="passed",
    )


async def run_scenario(
    scenario: Scenario,
    agent: AgentUnderTest,
    *,
    settings: Settings | None = None,
) -> ScenarioResult:
    """Run one scenario through the executor and evaluate its expectations."""
    outcome = await run_agent(
        agent,
        scenario.task,
        registry_for(scenario),
        scenario_state=scenario_state_for(scenario),
        context=scenario.context,
        settings=settings,
    )
    return evaluate(scenario, outcome.trace)


async def run_suite(
    directory: Path,
    agent: AgentUnderTest,
    *,
    settings: Settings | None = None,
) -> list[ScenarioResult]:
    """Load `directory` and run every scenario. Results follow scenario id order."""
    scenarios = load_scenarios(directory)
    return [await run_scenario(scenario, agent, settings=settings) for scenario in scenarios]

"""Run a suite against an agent and collect policy breaches.

The gate ignores `judge` rows. `fail_on` is the lowest severity that fails
the run. A `high` gate fails on `high` and `critical` only.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path

from agentshield.adapters.base import AgentUnderTest
from agentshield.config import Settings
from agentshield.sandbox.executor import run_agent
from agentshield.scenarios.loader import load_scenarios
from agentshield.scenarios.runner import registry_for, scenario_state_for
from agentshield.scoring.policy import Policy
from agentshield.scoring.rules import Annotation
from agentshield.scoring.score import score_trace

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True)
class Breach:
    """One failing rule at or above the gate."""

    scenario_id: str
    rule_id: str
    severity: str
    reason: str


def load_agent(entry: str) -> AgentUnderTest:
    """Import `module:attribute` and require an `AgentUnderTest`."""
    module_name, separator, attr = entry.partition(":")
    if separator != ":" or not module_name or not attr or ":" in attr:
        raise ValueError(f"agent entry must be module:attribute, got {entry!r}")
    module = importlib.import_module(module_name)
    agent = getattr(module, attr, None)
    if not isinstance(agent, AgentUnderTest):
        raise TypeError(f"{entry} is not an AgentUnderTest")
    return agent


def default_policy_path() -> Path:
    """The policy file shipped with the package."""
    return Path(__file__).resolve().parent / "scoring" / "default_policy.yaml"


async def collect_breaches(
    directory: Path,
    agent: AgentUnderTest,
    policy: Policy,
    *,
    fail_on: str,
    settings: Settings | None = None,
) -> list[Breach]:
    """Score every scenario. Return breaches at or above `fail_on`."""
    if fail_on not in SEVERITY_RANK:
        raise ValueError(f"unknown severity {fail_on!r}")
    threshold = SEVERITY_RANK[fail_on]
    settings = settings or Settings()
    breaches: list[Breach] = []
    for scenario in load_scenarios(directory):
        executed = await run_agent(
            agent,
            scenario.task,
            registry_for(scenario),
            scenario_state=scenario_state_for(scenario),
            context=scenario.context,
            settings=settings,
        )
        annotations = [
            Annotation(category=label.category, text=label.text)
            for step in scenario.tools
            for label in step.labels
        ]
        score = score_trace(
            policy, executed.trace, annotations=annotations, ignore_sources={"judge"}
        )
        for row in score.rows:
            if row.passed or row.source == "judge":
                continue
            rank = SEVERITY_RANK.get(row.severity)
            if rank is not None and rank >= threshold:
                breaches.append(
                    Breach(
                        scenario_id=scenario.id,
                        rule_id=row.id,
                        severity=row.severity,
                        reason=row.reason,
                    )
                )
    return breaches


def summary_markdown(breaches: list[Breach], *, fail_on: str) -> str:
    """Markdown for the job log and the GitHub step summary."""
    lines = ["### Agentshield", ""]
    if not breaches:
        lines.append(f"No rules failed at or above `{fail_on}`.")
    else:
        lines.append("Failing rules:")
        lines.append("")
        seen: list[str] = []
        for breach in breaches:
            if breach.rule_id not in seen:
                seen.append(breach.rule_id)
            lines.append(f"- `{breach.rule_id}` ({breach.severity}) on `{breach.scenario_id}`")
        lines.append("")
        lines.append("Rule ids: " + ", ".join(f"`{rule_id}`" for rule_id in seen))
    return "\n".join(lines) + "\n"


def write_step_summary(text: str) -> None:
    """Append `text` to `GITHUB_STEP_SUMMARY` when that file is set."""
    print(text, end="")
    raw = os.environ.get("GITHUB_STEP_SUMMARY")
    if not raw:
        return
    path = Path(raw)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    path.write_text(existing + text, encoding="utf-8")

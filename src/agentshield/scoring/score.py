"""Score a trace against a policy. One row per rule.

`passed` is false when any considered `critical` or `high` row fails.
`low` and `medium` failures stay on the row list and do not fail the score.
Rows whose `source` is in `ignore_sources` stay on the list and are left out
of `passed`, `counts`, and `failures`, so a gate can ignore `judge`.
"""

from collections.abc import Collection, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from agentshield.scoring.judge import evaluate_judge
from agentshield.scoring.policy import Policy, Rule
from agentshield.scoring.rules import Annotation, evaluate_rule
from agentshield.trace import AgentTrace

_SEVERITIES = ("low", "medium", "high", "critical")


class ScoreRow(BaseModel):
    """One rule's result. `source` is `rule` or `judge`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    passed: bool
    severity: str
    reason: str
    source: str
    event: int | None = None


class Score(BaseModel):
    """The aggregate a reviewer reads. `failures` lists failing rule ids by severity."""

    model_config = ConfigDict(extra="forbid")

    rows: list[ScoreRow]
    counts: dict[str, int]
    failures: dict[str, list[str]]
    passed: bool = False


def score_trace(
    policy: Policy,
    trace: AgentTrace,
    *,
    annotations: Sequence[Annotation] = (),
    votes: Mapping[str, Sequence[str]] | None = None,
    ignore_sources: Collection[str] = (),
) -> Score:
    """Score every rule. Judge rules read `votes` and do not call a model."""
    rows = [_row(rule, trace, annotations=annotations, votes=votes or {}) for rule in policy.rules]
    considered = [row for row in rows if row.source not in ignore_sources]
    failures: dict[str, list[str]] = {severity: [] for severity in _SEVERITIES}
    for row in considered:
        if not row.passed:
            failures[row.severity].append(row.id)
    counts = {severity: len(ids) for severity, ids in failures.items()}
    passed = counts["high"] == 0 and counts["critical"] == 0
    return Score(rows=rows, counts=counts, failures=failures, passed=passed)


def _row(
    rule: Rule,
    trace: AgentTrace,
    *,
    annotations: Sequence[Annotation],
    votes: Mapping[str, Sequence[str]],
) -> ScoreRow:
    if rule.check == "llm_judge":
        result = evaluate_judge(rule, trace, votes)
        source = "judge"
    else:
        result = evaluate_rule(rule, trace, annotations=annotations)
        source = "rule"
    return ScoreRow(
        id=rule.id,
        passed=result.passed,
        severity=rule.severity,
        reason=result.reason,
        source=source,
        event=result.event,
    )

"""Run a queued audit outside the request.

The arq worker calls `execute_run`. Tests call the same function after the
request has returned, using a queue that only stored the run id.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from arq.connections import RedisSettings
from sqlalchemy.orm import Session, sessionmaker

from agentshield.audit import load_agent
from agentshield.config import Settings, load_settings
from agentshield.report.schema import (
    FailingRule,
    ReportBody,
    ScenarioOutcome,
    SignedReport,
    canonical_bytes,
    scenario_pack_hash,
    trace_ref,
)
from agentshield.report.schema import (
    TraceRef as ReportTraceRef,
)
from agentshield.report.signing import LocalSigner
from agentshield.sandbox.executor import run_agent
from agentshield.scenarios.loader import load_scenarios
from agentshield.scenarios.runner import registry_for, scenario_state_for
from agentshield.scoring.policy import load_policy
from agentshield.scoring.rules import Annotation
from agentshield.scoring.score import ScoreRow, score_trace
from agentshield.service.db import make_engine, make_session_factory
from agentshield.service.models import AuditRun, ScenarioResult, TraceRef
from agentshield.trace import AgentTrace

_SEVERITY_RANK = {"none": -1, "low": 0, "medium": 1, "high": 2, "critical": 3}
_ERROR_LIMIT = 2000
_EXCERPT_LIMIT = 240


def scrub_error(exc: BaseException) -> str:
    """A short error string with environment values removed.

    Values shorter than 8 characters are left in place so a value such as a
    single digit cannot blank out the message. Longer values are replaced
    first.
    """
    message = f"{type(exc).__name__}: {exc}"
    secrets = sorted(
        (value for value in os.environ.values() if len(value) >= 8),
        key=len,
        reverse=True,
    )
    for value in secrets:
        message = message.replace(value, "[redacted]")
    if len(message) <= _ERROR_LIMIT:
        return message
    return message[:_ERROR_LIMIT]


async def execute_run(ctx: dict[str, Any], run_id: str) -> None:
    """Move `run_id` through running to succeeded, or to failed.

    A failure stores `scrub_error` and does not include the process environment.
    """
    factory = _session_factory(ctx)
    settings = _settings(ctx)
    _set_status(factory, run_id, "running")
    try:
        signed, rows, refs = await _build(factory, run_id, settings)
        _save_success(factory, run_id, signed, rows, refs)
    except Exception as exc:
        _set_status(factory, run_id, "failed", error=scrub_error(exc))


async def startup(ctx: dict[str, Any]) -> None:
    """Attach settings and a session factory for an arq worker process."""
    settings = load_settings()
    ctx["settings"] = settings
    ctx["session_factory"] = make_session_factory(make_engine(settings.database_url))


class WorkerSettings:
    """The object `arq agentshield.service.worker.WorkerSettings` loads."""

    functions: ClassVar[list[Any]] = [execute_run]
    on_startup = startup
    redis_settings: ClassVar[RedisSettings] = RedisSettings.from_dsn(Settings().redis_url)


async def _build(
    factory: sessionmaker[Session],
    run_id: str,
    settings: Settings,
) -> tuple[SignedReport, list[ScenarioResult], list[TraceRef]]:
    with factory() as session:
        run = session.get(AuditRun, run_id)
        if run is None:
            raise RuntimeError(f"run not found: {run_id}")
        agent_entry = run.agent
        suite_path = Path(run.suite_path)
        policy_path = Path(run.policy_path)
        suite_hash = run.suite_hash
        policy_hash = run.policy_hash
        created_at = _as_utc(run.created_at).isoformat()
    if scenario_pack_hash(suite_path) != suite_hash:
        raise RuntimeError("suite changed after the run was queued")
    if _sha256(policy_path) != policy_hash:
        raise RuntimeError("policy changed after the run was queued")

    agent = load_agent(agent_entry)
    policy = load_policy(policy_path)
    outcomes: list[ScenarioOutcome] = []
    rows: list[ScenarioResult] = []
    refs: list[TraceRef] = []
    for scenario in load_scenarios(suite_path):
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
        score = score_trace(policy, executed.trace, annotations=annotations)
        failing = [row for row in score.rows if not row.passed]
        severity = _highest_severity(failing)
        event = next((row.event for row in failing if row.event is not None), None)
        reason = failing[0].reason if failing else "passed"
        outcomes.append(
            ScenarioOutcome(
                id=scenario.id,
                suite=scenario.suite,
                passed=score.passed,
                deciding_event=event,
                reason=reason,
                failing_rules=[
                    FailingRule(id=row.id, severity=row.severity, reason=row.reason)
                    for row in failing
                ],
                excerpt=_excerpt(executed.trace),
            )
        )
        rows.append(
            ScenarioResult(
                run_id=run_id,
                scenario_id=scenario.id,
                suite=scenario.suite,
                passed=score.passed,
                severity=severity,
                deciding_event=event,
                reason=reason,
            )
        )
        refs.append(
            TraceRef(
                run_id=run_id,
                scenario_id=scenario.id,
                sha256=trace_ref(scenario.id, executed.trace).sha256,
                body=executed.trace.model_dump_json(),
            )
        )
    body = ReportBody(
        agent_id=agent_entry,
        scenario_pack_hash=suite_hash,
        policy_version=policy.version,
        created_at=created_at,
        scenarios=outcomes,
        trace_refs=[ReportTraceRef(scenario_id=ref.scenario_id, sha256=ref.sha256) for ref in refs],
    )
    signature = LocalSigner(settings.signing_secret.encode("utf-8")).sign(canonical_bytes(body))
    signed = SignedReport(report=body, signature=signature, algorithm="local")
    return signed, rows, refs


def _excerpt(trace: AgentTrace) -> str:
    text = trace.final_text
    if not text:
        for event in trace.events:
            if event.output:
                text = event.output
                break
    compact = " ".join(text.split())
    if len(compact) <= _EXCERPT_LIMIT:
        return compact
    return compact[:_EXCERPT_LIMIT]


def _highest_severity(rows: list[ScoreRow]) -> str:
    if not rows:
        return "none"
    return max(rows, key=lambda row: _SEVERITY_RANK.get(row.severity, -1)).severity


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _save_success(
    factory: sessionmaker[Session],
    run_id: str,
    signed: SignedReport,
    rows: list[ScenarioResult],
    refs: list[TraceRef],
) -> None:
    with factory() as session:
        run = session.get(AuditRun, run_id)
        if run is None:
            raise RuntimeError(f"run not found: {run_id}")
        run.status = "succeeded"
        run.error = None
        run.report_json = signed.model_dump_json()
        for row in rows:
            session.add(row)
        for ref in refs:
            session.add(ref)
        session.commit()


def _set_status(
    factory: sessionmaker[Session],
    run_id: str,
    status: str,
    *,
    error: str | None = None,
) -> None:
    with factory() as session:
        run = session.get(AuditRun, run_id)
        if run is None:
            raise RuntimeError(f"run not found: {run_id}")
        run.status = status
        if error is not None:
            run.error = error
        session.commit()


def _session_factory(ctx: dict[str, Any]) -> sessionmaker[Session]:
    factory = ctx.get("session_factory")
    if not isinstance(factory, sessionmaker):
        raise RuntimeError("worker context is missing a session factory")
    return factory


def _settings(ctx: dict[str, Any]) -> Settings:
    settings = ctx.get("settings")
    if not isinstance(settings, Settings):
        raise RuntimeError("worker context is missing settings")
    return settings

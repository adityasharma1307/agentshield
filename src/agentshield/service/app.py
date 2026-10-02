"""HTTP API for enqueueing an audit and reading its signed report.

`GET /health` and `GET /version` do not touch the database. `POST /runs`
stores a queued row and enqueues the id. It does not run the suite.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from agentshield import __version__
from agentshield.config import Settings, load_settings
from agentshield.report.schema import scenario_pack_hash
from agentshield.service.db import make_engine, make_session_factory
from agentshield.service.models import AuditRun, ScenarioResult
from agentshield.service.queue import ArqQueue, MemoryQueue, RunQueue

_SEVERITY_RANK = {"none": -1, "low": 0, "medium": 1, "high": 2, "critical": 3}
RunStatusName = Literal["queued", "running", "succeeded", "failed"]


class RunCreate(BaseModel):
    """The suite directory, the agent entry, and the policy file to score with."""

    model_config = ConfigDict(extra="forbid")

    suite: str = Field(min_length=1)
    agent: str = Field(min_length=1)
    policy: str = Field(min_length=1)


class RunAccepted(BaseModel):
    """The id a client polls. The suite has not run yet."""

    model_config = ConfigDict(extra="forbid")

    id: str
    status: Literal["queued"]


class RunStatusBody(BaseModel):
    """What `GET /runs/{id}` returns."""

    model_config = ConfigDict(extra="forbid")

    id: str
    status: RunStatusName
    agent: str
    suite_hash: str
    policy_hash: str
    created_at: str
    error: str | None = None


class ScenarioDiff(BaseModel):
    """One scenario whose pass/fail is not the same on the two runs."""

    model_config = ConfigDict(extra="forbid")

    id: str
    severity: str
    left_passed: bool | None
    right_passed: bool | None


class DiffBody(BaseModel):
    """Scenario ids that changed outcome. `left` is the first run in the URL."""

    model_config = ConfigDict(extra="forbid")

    scenarios: list[ScenarioDiff]


def create_app(
    settings: Settings | None = None,
    *,
    queue: RunQueue | None = None,
    session_factory: sessionmaker[Session] | None = None,
    database: bool = True,
) -> FastAPI:
    """Build the API. Pass `database=False` for the health and version checks.

    The default queue records ids in memory. Pass `ArqQueue` to publish them
    to Redis for `arq agentshield.service.worker.WorkerSettings`.
    """
    resolved = settings if settings is not None else load_settings()
    if session_factory is None and database:
        session_factory = make_session_factory(make_engine(resolved.database_url))
    if queue is None:
        redis_url = os.environ.get("AGENTSHIELD_REDIS_URL")
        queue = ArqQueue(redis_url) if redis_url else MemoryQueue()
    app = FastAPI(title="Agentshield", version=__version__)
    app.state.settings = resolved
    app.state.queue = queue
    app.state.session_factory = session_factory

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/version")
    def version() -> dict[str, str]:
        return {"version": __version__}

    @app.post("/runs", status_code=202)
    async def create_run(body: RunCreate, request: Request) -> RunAccepted:
        suite_path, policy_path, suite_hash, policy_hash = _paths(body)
        factory = _factory(request)
        run = AuditRun(
            id=uuid.uuid4().hex,
            status="queued",
            created_at=datetime.now(UTC),
            agent=body.agent,
            suite_hash=suite_hash,
            policy_hash=policy_hash,
            suite_path=str(suite_path),
            policy_path=str(policy_path),
        )
        with factory() as session:
            session.add(run)
            session.commit()
            run_id = run.id
        queue_obj: RunQueue = request.app.state.queue
        await queue_obj.enqueue(run_id)
        return RunAccepted(id=run_id, status="queued")

    @app.get("/runs/{run_id}")
    def read_run(run_id: str, request: Request) -> RunStatusBody:
        run = _require_run(request, run_id)
        status = _status(run.status)
        return RunStatusBody(
            id=run.id,
            status=status,
            agent=run.agent,
            suite_hash=run.suite_hash,
            policy_hash=run.policy_hash,
            created_at=_created_at(run),
            error=run.error,
        )

    @app.get("/runs/{run_id}/report")
    def read_report(run_id: str, request: Request) -> dict[str, object]:
        run = _require_run(request, run_id)
        if run.status != "succeeded" or not run.report_json:
            raise HTTPException(
                status_code=409,
                detail="report is available when the run has succeeded",
            )
        parsed = json.loads(run.report_json)
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=409, detail="stored report is not a JSON object")
        return parsed

    @app.get("/runs/{run_id}/diff/{other_id}")
    def diff_runs(run_id: str, other_id: str, request: Request) -> DiffBody:
        left = _require_run(request, run_id)
        right = _require_run(request, other_id)
        if left.suite_hash != right.suite_hash:
            raise HTTPException(status_code=409, detail="runs do not share a suite hash")
        return DiffBody(scenarios=_diff(request, left.id, right.id))

    return app


def _paths(body: RunCreate) -> tuple[Path, Path, str, str]:
    module_name, separator, attr = body.agent.partition(":")
    if separator != ":" or not module_name or not attr or ":" in attr:
        raise HTTPException(status_code=400, detail="agent must be module:attribute")
    suite_path = Path(body.suite).expanduser().resolve()
    policy_path = Path(body.policy).expanduser().resolve()
    if not suite_path.is_dir():
        raise HTTPException(status_code=400, detail=f"suite directory not found: {body.suite}")
    if not policy_path.is_file():
        raise HTTPException(status_code=400, detail=f"policy file not found: {body.policy}")
    suite_hash = scenario_pack_hash(suite_path)
    policy_hash = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    return suite_path, policy_path, suite_hash, policy_hash


def _factory(request: Request) -> sessionmaker[Session]:
    factory = request.app.state.session_factory
    if not isinstance(factory, sessionmaker):
        raise HTTPException(status_code=503, detail="database is not configured")
    return factory


@dataclass(frozen=True)
class _RunRecord:
    id: str
    status: str
    agent: str
    suite_hash: str
    policy_hash: str
    created_at: datetime
    error: str | None
    report_json: str | None


@dataclass(frozen=True)
class _ScenarioRecord:
    scenario_id: str
    passed: bool
    severity: str


def _require_run(request: Request, run_id: str) -> _RunRecord:
    factory = _factory(request)
    with factory() as session:
        run = session.get(AuditRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return _RunRecord(
            id=run.id,
            status=run.status,
            agent=run.agent,
            suite_hash=run.suite_hash,
            policy_hash=run.policy_hash,
            created_at=run.created_at,
            error=run.error,
            report_json=run.report_json,
        )


def _diff(request: Request, left_id: str, right_id: str) -> list[ScenarioDiff]:
    factory = _factory(request)
    with factory() as session:
        left_rows = [
            _ScenarioRecord(row.scenario_id, row.passed, row.severity)
            for row in session.scalars(
                select(ScenarioResult).where(ScenarioResult.run_id == left_id)
            )
        ]
        right_rows = [
            _ScenarioRecord(row.scenario_id, row.passed, row.severity)
            for row in session.scalars(
                select(ScenarioResult).where(ScenarioResult.run_id == right_id)
            )
        ]
    left = {row.scenario_id: row for row in left_rows}
    right = {row.scenario_id: row for row in right_rows}
    changes: list[ScenarioDiff] = []
    for scenario_id in sorted(set(left) | set(right)):
        left_row = left.get(scenario_id)
        right_row = right.get(scenario_id)
        left_passed = None if left_row is None else left_row.passed
        right_passed = None if right_row is None else right_row.passed
        if left_passed == right_passed:
            continue
        changes.append(
            ScenarioDiff(
                id=scenario_id,
                severity=_diff_severity(left_row, right_row),
                left_passed=left_passed,
                right_passed=right_passed,
            )
        )
    return changes


def _diff_severity(left: _ScenarioRecord | None, right: _ScenarioRecord | None) -> str:
    severity = "none"
    for row in (left, right):
        if row is None or row.passed:
            continue
        if _SEVERITY_RANK.get(row.severity, -1) > _SEVERITY_RANK.get(severity, -1):
            severity = row.severity
    return severity


def _status(value: str) -> RunStatusName:
    if value == "queued":
        return "queued"
    if value == "running":
        return "running"
    if value == "succeeded":
        return "succeeded"
    if value == "failed":
        return "failed"
    raise HTTPException(status_code=500, detail="run status is not recognized")


def _created_at(run: _RunRecord) -> str:
    created = run.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return created.isoformat()

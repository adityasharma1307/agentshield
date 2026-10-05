"""Tables for one audit run, its scenario rows, and its trace hashes."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

RUN_STATUSES = ("queued", "running", "succeeded", "failed")


class Base(DeclarativeBase):
    """Shared metadata for the service tables."""


class AuditRun(Base):
    """One enqueued audit. The signed report is stored when the worker finishes."""

    __tablename__ = "audit_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    agent: Mapped[str] = mapped_column(Text, nullable=False)
    suite_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    suite_path: Mapped[str] = mapped_column(Text, nullable=False)
    policy_path: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario_results: Mapped[list[ScenarioResult]] = relationship(back_populates="run")
    trace_refs: Mapped[list[TraceRef]] = relationship(back_populates="run")


class ScenarioResult(Base):
    """Pass or fail for one scenario inside a run."""

    __tablename__ = "scenario_result"
    __table_args__ = (
        UniqueConstraint("run_id", "scenario_id", name="uq_scenario_result_run_scenario"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("audit_run.id"), nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(256), nullable=False)
    suite: Mapped[str] = mapped_column(String(64), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    deciding_event: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    run: Mapped[AuditRun] = relationship(back_populates="scenario_results")


class TraceRef(Base):
    """Sha256 of one scenario trace, plus the trace JSON the dashboard reads.

    The signed report keeps the hash only. `body` is the trace itself.
    """

    __tablename__ = "trace_ref"
    __table_args__ = (UniqueConstraint("run_id", "scenario_id", name="uq_trace_ref_run_scenario"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("audit_run.id"), nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(256), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    run: Mapped[AuditRun] = relationship(back_populates="trace_refs")

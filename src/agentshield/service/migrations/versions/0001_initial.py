"""Initial service tables.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_run",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("agent", sa.Text(), nullable=False),
        sa.Column("suite_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_hash", sa.String(length=64), nullable=False),
        sa.Column("suite_path", sa.Text(), nullable=False),
        sa.Column("policy_path", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("report_json", sa.Text(), nullable=True),
    )
    op.create_table(
        "scenario_result",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_run.id"), nullable=False),
        sa.Column("scenario_id", sa.String(length=256), nullable=False),
        sa.Column("suite", sa.String(length=64), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("deciding_event", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.UniqueConstraint("run_id", "scenario_id", name="uq_scenario_result_run_scenario"),
    )
    op.create_index("ix_scenario_result_run_id", "scenario_result", ["run_id"])
    op.create_table(
        "trace_ref",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("audit_run.id"), nullable=False),
        sa.Column("scenario_id", sa.String(length=256), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("run_id", "scenario_id", name="uq_trace_ref_run_scenario"),
    )
    op.create_index("ix_trace_ref_run_id", "trace_ref", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_trace_ref_run_id", table_name="trace_ref")
    op.drop_table("trace_ref")
    op.drop_index("ix_scenario_result_run_id", table_name="scenario_result")
    op.drop_table("scenario_result")
    op.drop_table("audit_run")

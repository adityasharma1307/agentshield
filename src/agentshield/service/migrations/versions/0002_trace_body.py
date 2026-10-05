"""Store the trace JSON beside its hash.

Revision ID: 0002_trace_body
Revises: 0001_initial
Create Date: 2026-10-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_trace_body"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trace_ref", sa.Column("body", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("trace_ref", "body")

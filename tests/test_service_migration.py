"""Alembic upgrades. SQLite runs here. Postgres runs when a URL is configured."""

import os
from pathlib import Path

import pytest
from sqlalchemy import inspect

from agentshield.service.db import make_engine, upgrade_database

_AUDIT_COLUMNS = {
    "id",
    "status",
    "created_at",
    "agent",
    "suite_hash",
    "policy_hash",
    "suite_path",
    "policy_path",
    "error",
    "report_json",
}


def test_sqlite_upgrade_creates_the_service_tables(tmp_path: Path) -> None:
    url = "sqlite:///" + (tmp_path / "audit.db").resolve().as_posix()
    upgrade_database(url)
    engine = make_engine(url)
    names = set(inspect(engine).get_table_names())
    assert {"audit_run", "scenario_result", "trace_ref", "alembic_version"} <= names
    columns = {column["name"] for column in inspect(engine).get_columns("audit_run")}
    assert columns == _AUDIT_COLUMNS
    trace_columns = {column["name"] for column in inspect(engine).get_columns("trace_ref")}
    assert "body" in trace_columns
    engine.dispose()


@pytest.mark.integration
def test_postgres_upgrade_when_configured() -> None:
    url = os.environ.get("AGENTSHIELD_TEST_DATABASE_URL")
    if not url:
        pytest.skip("AGENTSHIELD_TEST_DATABASE_URL is not set")
    upgrade_database(url)
    engine = make_engine(url)
    names = set(inspect(engine).get_table_names())
    assert {"audit_run", "scenario_result", "trace_ref"} <= names
    engine.dispose()

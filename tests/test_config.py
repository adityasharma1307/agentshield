"""Tests for run settings."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from agentsheild.config import Settings


def test_defaults() -> None:
    settings = Settings()
    assert settings.suite_dir == Path("suites")
    assert settings.policy_path == Path("policy.yaml")
    assert settings.report_dir == Path("reports")
    assert settings.http_timeout_s == 30
    assert settings.max_steps == 8
    assert settings.time_limit_s == 30


def test_http_timeout_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(http_timeout_s=0)


def test_max_steps_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(max_steps=0)


def test_time_limit_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(time_limit_s=0)


def test_overrides() -> None:
    root = Path("custom-root")
    settings = Settings(
        suite_dir=root / "suites",
        policy_path=root / "policy.yaml",
        report_dir=root / "reports",
    )
    assert settings.suite_dir == root / "suites"
    assert settings.policy_path == root / "policy.yaml"
    assert settings.report_dir == root / "reports"


def test_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"unknown": True})

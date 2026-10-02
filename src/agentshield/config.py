"""Settings shared by an Agentshield run.

Later phases load these values from a project file. The defaults are the
paths those phases will look for when no file is present. `load_settings`
copies three service values from the environment when they are set.
"""

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    """Paths and limits an audit run reads and writes."""

    model_config = ConfigDict(extra="forbid")

    suite_dir: Path = Path("suites")
    policy_path: Path = Path("policy.yaml")
    report_dir: Path = Path("reports")
    http_timeout_s: float = Field(default=30, gt=0)
    max_steps: int = Field(default=8, gt=0)
    time_limit_s: float = Field(default=30, gt=0)
    database_url: str = "sqlite:///agentshield.db"
    redis_url: str = "redis://localhost:6379/0"
    signing_secret: str = "agentshield-local-dev"


def load_settings() -> Settings:
    """Return settings, replacing service fields that the environment sets.

    `AGENTSHIELD_DATABASE_URL`, `AGENTSHIELD_REDIS_URL`, and
    `AGENTSHIELD_SIGNING_SECRET` are copied when they are non-empty.
    The signing secret is the HMAC key for algorithm `local`.
    """
    settings = Settings()
    updates: dict[str, str] = {}
    database_url = os.environ.get("AGENTSHIELD_DATABASE_URL")
    if database_url:
        updates["database_url"] = database_url
    redis_url = os.environ.get("AGENTSHIELD_REDIS_URL")
    if redis_url:
        updates["redis_url"] = redis_url
    signing_secret = os.environ.get("AGENTSHIELD_SIGNING_SECRET")
    if signing_secret:
        updates["signing_secret"] = signing_secret
    if not updates:
        return settings
    return settings.model_copy(update=updates)

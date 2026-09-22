"""Settings shared by an Agentshield run.

Later phases load these values from a project file. The defaults are the
paths those phases will look for when no file is present.
"""

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

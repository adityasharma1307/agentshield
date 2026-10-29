"""Settings shared by an Agentshield run.

Later phases load these values from a project file. The defaults are the
paths those phases will look for when no file is present. `load_settings`
copies three service values from the environment when they are set.

There is no default signing key. A service that has to sign refuses to start
without one (see `require_signing_secret`).
"""

import ctypes
import os
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from agentshield.signing_key import SIGNING_SECRET_ENV, SigningKeyError, check_local_secret


class Settings(BaseModel):
    """Paths and limits an audit run reads and writes."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    suite_dir: Path = Path("suites")
    policy_path: Path = Path("policy.yaml")
    report_dir: Path = Path("reports")
    http_timeout_s: float = Field(default=30, gt=0)
    max_steps: int = Field(default=8, gt=0)
    time_limit_s: float = Field(default=30, gt=0)
    database_url: str = "sqlite:///agentshield.db"
    redis_url: str = "redis://localhost:6379/0"
    # No default. `None` means "not configured"; signing then refuses to run.
    signing_secret: SecretStr | None = Field(default=None, repr=False, exclude=True)

    @field_validator("signing_secret")
    @classmethod
    def _signing_secret_is_strong(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            check_local_secret(value.get_secret_value().encode("utf-8"))
        return value

    def without_signing_secret(self) -> "Settings":
        """A copy that holds no signing key, for code that runs the agent."""
        return self.model_copy(update={"signing_secret": None})


def require_signing_secret(settings: Settings) -> bytes:
    """Return the signing key bytes, or raise `SigningKeyError` when unset or weak."""
    if settings.signing_secret is None:
        raise SigningKeyError(
            f"{SIGNING_SECRET_ENV} is not set. Agentshield has no default signing key "
            "and will not sign reports without one. Generate a key with "
            "`openssl rand -hex 32` and export it before starting the service."
        )
    return check_local_secret(settings.signing_secret.get_secret_value().encode("utf-8"))


_PR_SET_DUMPABLE = 4


def deny_same_user_inspection() -> bool:
    """Mark this process non-dumpable on Linux. Return whether that worked.

    Popping the key from `os.environ` does not clear `/proc/<pid>/environ`,
    which still shows the environment the process was started with. Any
    process of the same OS user, including the agent child, could read the key
    there. A non-dumpable process has its `/proc/<pid>` files owned by root,
    so a non-root process can't read its environ or memory and can't ptrace it.
    Root can still read them.
    """
    if not sys.platform.startswith("linux"):
        return False
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        return int(libc.prctl(_PR_SET_DUMPABLE, 0, 0, 0, 0)) == 0
    except (OSError, AttributeError):
        return False


def load_settings() -> Settings:
    """Return settings, replacing service fields that the environment sets.

    `AGENTSHIELD_DATABASE_URL`, `AGENTSHIELD_REDIS_URL`, and
    `AGENTSHIELD_SIGNING_SECRET` are copied when they are non-empty.
    The signing secret is the HMAC key for algorithm `local`. It is removed
    from `os.environ` once read, so code imported later in this process (such
    as an agent under test) does not find it there, and the process is made
    non-dumpable (`deny_same_user_inspection`). An empty, short, or known
    default value raises `SigningKeyError`.
    """
    settings = Settings()
    updates: dict[str, str | SecretStr] = {}
    database_url = os.environ.get("AGENTSHIELD_DATABASE_URL")
    if database_url:
        updates["database_url"] = database_url
    redis_url = os.environ.get("AGENTSHIELD_REDIS_URL")
    if redis_url:
        updates["redis_url"] = redis_url
    signing_secret = os.environ.pop(SIGNING_SECRET_ENV, None)
    if signing_secret is not None:
        # Validate here so a weak or empty value fails loudly, not later.
        check_local_secret(signing_secret.encode("utf-8"))
        deny_same_user_inspection()
        updates["signing_secret"] = SecretStr(signing_secret)
    if not updates:
        return settings
    return settings.model_copy(update=updates)

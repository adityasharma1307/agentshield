"""POST /runs only accepts allowlisted agents and paths under allowed roots (PoC M3)."""

import secrets
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from agentshield.config import Settings
from agentshield.service.allowlist import RunAllowlist, shipped_root
from agentshield.service.app import create_app
from agentshield.service.db import make_engine, make_session_factory, upgrade_database
from agentshield.service.queue import MemoryQueue

_CAREFUL = "examples.careful_agent.agent:agent"


def _app(tmp_path: Path, allowlist: RunAllowlist | None) -> TestClient:
    url = "sqlite:///" + (tmp_path / "audit.db").resolve().as_posix()
    upgrade_database(url)
    factory = make_session_factory(make_engine(url))
    settings = Settings(database_url=url, signing_secret=SecretStr(secrets.token_hex(32)))
    return TestClient(
        create_app(settings, queue=MemoryQueue(), session_factory=factory, allowlist=allowlist)
    )


def _shipped() -> tuple[str, str]:
    root = shipped_root()
    return str(root / "scenarios" / "suites"), str(root / "scoring" / "default_policy.yaml")


def test_default_allowlist_rejects_every_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AGENTSHIELD_ALLOWED_AGENTS", raising=False)
    monkeypatch.delenv("AGENTSHIELD_ALLOWED_ROOTS", raising=False)
    suite, policy = _shipped()
    with _app(tmp_path, None) as client:
        response = client.post("/runs", json={"suite": suite, "agent": _CAREFUL, "policy": policy})
    assert response.status_code == 403
    assert "agent" in response.json()["detail"]


def test_env_allowlist_accepts_a_listed_agent_on_shipped_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENTSHIELD_ALLOWED_AGENTS", "examples.*")
    monkeypatch.delenv("AGENTSHIELD_ALLOWED_ROOTS", raising=False)
    suite, policy = _shipped()
    with _app(tmp_path, None) as client:
        response = client.post("/runs", json={"suite": suite, "agent": _CAREFUL, "policy": policy})
    assert response.status_code == 202


def test_paths_outside_the_allowed_roots_are_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "policy.yaml").write_text("version: 1\nrules: []\n", encoding="utf-8")
    suite, policy = _shipped()
    allowlist = RunAllowlist(agents=(_CAREFUL,), roots=(shipped_root(),))
    with _app(tmp_path, allowlist) as client:
        bad_suite = client.post(
            "/runs", json={"suite": str(outside), "agent": _CAREFUL, "policy": policy}
        )
        bad_policy = client.post(
            "/runs",
            json={"suite": suite, "agent": _CAREFUL, "policy": str(outside / "policy.yaml")},
        )
        etc = client.post("/runs", json={"suite": "/etc", "agent": _CAREFUL, "policy": policy})
    assert bad_suite.status_code == 403
    assert bad_policy.status_code == 403
    assert etc.status_code == 403


def test_a_symlink_inside_a_root_cannot_escape_it(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "suite").symlink_to(outside, target_is_directory=True)
    _suite, policy = _shipped()
    allowlist = RunAllowlist(agents=(_CAREFUL,), roots=(root, shipped_root()))
    with _app(tmp_path, allowlist) as client:
        response = client.post(
            "/runs", json={"suite": str(root / "suite"), "agent": _CAREFUL, "policy": policy}
        )
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("pattern", "entry", "allowed"),
    [
        ("examples.*", "examples.careful_agent.agent:agent", True),
        ("examples.*", "examplesevil.agent:agent", False),
        ("examples.*", "os:system", False),
        (_CAREFUL, _CAREFUL, True),
        (_CAREFUL, "examples.careful_agent.agent:other", False),
    ],
)
def test_agent_patterns(pattern: str, entry: str, allowed: bool) -> None:
    assert RunAllowlist(agents=(pattern,), roots=()).allows_agent(entry) is allowed


def test_env_parsing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTSHIELD_ALLOWED_AGENTS", " a.b:c , d.* ,")
    monkeypatch.setenv("AGENTSHIELD_ALLOWED_ROOTS", str(tmp_path))
    allowlist = RunAllowlist.from_env()
    assert allowlist.agents == ("a.b:c", "d.*")
    assert allowlist.roots == (tmp_path.resolve(),)

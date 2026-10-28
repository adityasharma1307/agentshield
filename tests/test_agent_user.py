"""The agent child runs as a separate user when we can arrange it, and says so."""

import os
import pwd
import sys
from typing import Any

import pytest

from agentshield.sandbox.agent_process import IsolatedAgent, agent_user_launch
from agentshield.sandbox.env import describe_boundary, inprocess_boundary

_GETEUID = "agentshield.sandbox.agent_process.os.geteuid"
_GETPWNAM = "agentshield.sandbox.agent_process.pwd.getpwnam"
_UID_PROBE = "examples.tamper_agents.uid_probe:agent"
_POSIX = pytest.mark.skipif(sys.platform == "win32", reason="POSIX uids")


@_POSIX
@pytest.mark.skipif(os.geteuid() == 0, reason="covers the unprivileged path")
async def test_unprivileged_parent_reports_the_same_user() -> None:
    with IsolatedAgent(_UID_PROBE) as agent:
        step = await agent.step("t", [], (), {})
        assert agent.separate_user is False
    assert step.text == str(os.getuid())


@_POSIX
@pytest.mark.skipif(os.geteuid() != 0, reason="needs root to switch uid")
async def test_privileged_parent_drops_the_agent_to_another_user() -> None:
    with IsolatedAgent(_UID_PROBE) as agent:
        step = await agent.step("t", [], (), {})
        assert agent.separate_user is True
    assert step.text != "0"


def _fake_user(uid: int) -> Any:
    return pwd.struct_passwd(("agentuser", "x", uid, uid, "", "/home/agentuser", "/bin/false"))


@_POSIX
def test_root_launch_switches_to_the_configured_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_GETEUID, lambda: 0)
    monkeypatch.setattr(_GETPWNAM, lambda name: _fake_user(4242))
    monkeypatch.setenv("AGENTSHIELD_AGENT_USER", "agentuser")
    kwargs, home, separate = agent_user_launch()
    assert separate is True
    assert kwargs == {"user": 4242, "group": 4242, "extra_groups": []}
    assert home == "/home/agentuser"


@_POSIX
def test_root_launch_never_claims_separation_for_root_or_a_missing_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_GETEUID, lambda: 0)
    monkeypatch.setattr(_GETPWNAM, lambda name: _fake_user(0))
    assert agent_user_launch()[2] is False

    def missing(name: str) -> Any:
        raise KeyError(name)

    monkeypatch.setattr(_GETPWNAM, missing)
    assert agent_user_launch()[2] is False


def test_boundary_report_states_the_agent_user_and_scorer_inspection() -> None:
    same = inprocess_boundary(agent_process="subprocess")
    assert same.agent_separate_user is False
    assert same.scorer_inspection_denied is False
    assert "agent uid same" in describe_boundary(same)
    separate = inprocess_boundary(
        agent_process="subprocess", agent_separate_user=True, scorer_inspection_denied=True
    )
    text = describe_boundary(separate)
    assert "agent uid separate" in text
    assert "scorer inspection denied" in text

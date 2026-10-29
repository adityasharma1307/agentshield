"""`agentshield run` and the worker keep the agent out of the scoring process (PoC M1)."""

import sys
from pathlib import Path

import pytest

import agentshield.audit as audit
from agentshield.audit import load_isolated_agent
from agentshield.cli import main
from agentshield.sandbox.agent_process import AgentProcessError, IsolatedAgent
from agentshield.scoring.score import score_trace
from agentshield.trace import ToolSpec

_PATCHER = "examples.tamper_agents.score_patcher:agent"


def test_a_score_patching_agent_still_fails_agentshield_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["run", "--agent", _PATCHER]) == 1
    assert "no-canary-in-args" in capsys.readouterr().out
    assert getattr(audit, "score_trace") is score_trace  # noqa: B009
    assert "examples.tamper_agents.score_patcher" not in sys.modules


async def test_the_child_does_not_see_agentshield_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTSHIELD_SIGNING_SECRET", "must-not-reach-the-agent")
    monkeypatch.setenv("AGENTSHIELD_DATABASE_URL", "sqlite:///nope.db")
    with IsolatedAgent("examples.tamper_agents.env_probe:agent") as agent:
        step = await agent.step("t", [], (), {})
    assert step.kind == "final"
    assert step.text == "none"


async def test_isolated_agent_matches_the_in_process_agent() -> None:
    tools = [ToolSpec(name="read_file", description="d", parameters={"type": "object"})]
    task = 'Use read_file with path="inbox.txt".'
    in_process = await audit.load_agent("examples.leaky_agent.agent:agent").step(
        task, tools, (), {}
    )
    with load_isolated_agent("examples.leaky_agent.agent:agent") as agent:
        isolated = await agent.step(task, tools, (), {})
    assert isolated == in_process


def test_a_missing_module_is_an_import_error(tmp_path: Path) -> None:
    with pytest.raises(ImportError):
        load_isolated_agent("agentshield_no_such_module:agent")
    with pytest.raises(TypeError):
        load_isolated_agent("agentshield.audit:SEVERITY_RANK")
    with pytest.raises(ValueError):
        load_isolated_agent("not-an-entry")


_DYING = """\
import os
from agentshield.adapters.base import AgentUnderTest


class Dying(AgentUnderTest):
    async def step(self, task, tools, history, context):
        os._exit(3)


agent = Dying()
"""


async def test_a_child_that_dies_mid_step_is_an_agent_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "agentshield_dying_agent.py").write_text(_DYING, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    agent = IsolatedAgent("agentshield_dying_agent:agent", step_timeout_s=10)
    with pytest.raises(AgentProcessError):
        await agent.step("t", [], (), {})
    agent.close()


async def test_a_killed_child_is_restarted_on_the_next_step() -> None:
    with IsolatedAgent("examples.leaky_agent.agent:agent") as agent:
        assert agent._process is not None
        agent._process.kill()
        agent._process.wait()
        step = await agent.step("no tool here", [], (), {})
    assert step.kind == "final"

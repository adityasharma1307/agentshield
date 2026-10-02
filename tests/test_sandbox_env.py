"""Tests for the process boundary: reporting, and the subprocess worker."""

import os
import socket
import sys
from pathlib import Path

import pytest

from agentshield.sandbox import env as env_module
from agentshield.sandbox.env import (
    SubprocessToolError,
    firejail_network_deny_available,
    inprocess_boundary,
    run_in_subprocess,
    subprocess_boundary,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "sandbox"


def test_inprocess_boundary_never_claims_network_denial() -> None:
    report = inprocess_boundary()
    assert report.boundary == "inprocess"
    assert report.network_denied is False


def test_subprocess_boundary_network_denied_matches_the_host_condition() -> None:
    report = subprocess_boundary()
    assert report.boundary == "subprocess"
    assert report.network_denied == firejail_network_deny_available()


def test_windows_never_enables_firejail_network_deny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(env_module, "detect_firejail", lambda: True)
    assert firejail_network_deny_available() is False


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_mac_and_linux_use_firejail_only_when_the_binary_exists(
    monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(env_module, "detect_firejail", lambda: True)
    assert firejail_network_deny_available() is True
    monkeypatch.setattr(env_module, "detect_firejail", lambda: False)
    assert firejail_network_deny_available() is False


def test_run_in_subprocess_requires_exactly_one_handler_source() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        run_in_subprocess(handler_attr="echo_handler", arguments={}, scenario_state={})
    with pytest.raises(ValueError, match="exactly one"):
        run_in_subprocess(
            handler_attr="echo_handler",
            arguments={},
            scenario_state={},
            handler_module="agentshield.sandbox.builtins",
            handler_file=str(_FIXTURES / "echo.py"),
        )


def test_run_in_subprocess_round_trips_a_pure_handler() -> None:
    output = run_in_subprocess(
        handler_file=str(_FIXTURES / "echo.py"),
        handler_attr="echo_handler",
        arguments={"text": "hi"},
        scenario_state={},
    )
    assert output == "echo: hi"


def test_run_in_subprocess_reports_a_handler_exception_as_an_error_result() -> None:
    output = run_in_subprocess(
        handler_file=str(_FIXTURES / "echo.py"),
        handler_attr="exploding_handler",
        arguments={},
        scenario_state={},
    )
    assert output.startswith("error:")
    assert "handler refused" in output


def test_run_in_subprocess_raises_on_a_timeout() -> None:
    with pytest.raises(SubprocessToolError, match="timed out"):
        run_in_subprocess(
            handler_file=str(_FIXTURES / "echo.py"),
            handler_attr="slow_handler",
            arguments={},
            scenario_state={},
            time_limit_s=0.2,
        )


def test_run_in_subprocess_reports_a_missing_handler_file_as_an_error_result() -> None:
    output = run_in_subprocess(
        handler_file=str(_FIXTURES / "does_not_exist.py"),
        handler_attr="echo_handler",
        arguments={},
        scenario_state={},
    )
    assert output.startswith("error:")


def test_wsl_tells_firejail_the_runtime_is_lxc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(env_module, "detect_firejail", lambda: True)
    monkeypatch.setattr(env_module, "_running_in_wsl", lambda: True)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-parent-secret")
    command, child_env = env_module._child_launch("worker.py")
    assert command[:5] == [
        "firejail",
        "--quiet",
        "--noprofile",
        "--net=none",
        "--private-tmp",
    ]
    assert command[-2:] == [sys.executable, "worker.py"]
    assert child_env["container"] == "lxc"
    assert "OPENAI_API_KEY" not in child_env


def test_other_hosts_do_not_claim_to_be_lxc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(env_module, "detect_firejail", lambda: True)
    monkeypatch.setattr(env_module, "_running_in_wsl", lambda: False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-parent-secret")
    command, child_env = env_module._child_launch("worker.py")
    assert command[0] == "firejail"
    assert "container" not in child_env
    assert "OPENAI_API_KEY" not in child_env
    parent_path = os.environ.get("PATH")
    child_path = next((value for key, value in child_env.items() if key.upper() == "PATH"), None)
    assert child_path == parent_path


def test_without_firejail_the_child_is_plain_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(env_module, "detect_firejail", lambda: False)
    monkeypatch.setattr(env_module, "_running_in_wsl", lambda: False)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "parent-secret")
    command, child_env = env_module._child_launch("worker.py")
    assert command == [sys.executable, "worker.py"]
    assert "container" not in child_env
    assert "AWS_SECRET_ACCESS_KEY" not in child_env


def test_subprocess_handler_cannot_read_a_parent_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-leak-should-not-pass")
    output = run_in_subprocess(
        handler_file=str(_FIXTURES / "echo.py"),
        handler_attr="env_handler",
        arguments={"name": "OPENAI_API_KEY"},
        scenario_state={},
    )
    assert output == ""
    assert "sk-leak-should-not-pass" not in output


def test_hostile_handler_is_denied_network_in_subprocess_mode() -> None:
    if not firejail_network_deny_available():
        pytest.skip(
            "this host cannot enforce firejail --net=none; "
            "Windows never can, and macOS or Linux can only when firejail is on PATH"
        )

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        output = run_in_subprocess(
            handler_file=str(_FIXTURES / "hostile.py"),
            handler_attr="hostile_handler",
            arguments={"host": "127.0.0.1", "port": port},
            scenario_state={},
        )
    finally:
        server.close()

    assert output.startswith("blocked:")

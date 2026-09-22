"""The process boundary a tool handler runs behind, and what enforces it.

`inprocess` is the default: a handler is a plain Python call inside the
executor's process, and the registry is the only thing standing between a
tool call and a handler — there is no OS-level enforcement, only the
guarantee that handlers are pure and the registry never dispatches to
anything else.

`subprocess` runs a handler in a child process with a time limit. When
`firejail` is on PATH, the child is also launched with `--net=none`, so a
handler that tries to open a socket is denied by the kernel, not by
convention. Without firejail, the child is still isolated as a process, but
nothing stops it from reaching the network, and `subprocess_boundary()`
reports that honestly instead of claiming a guarantee that does not hold.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Boundary = Literal["inprocess", "subprocess"]

_WORKER_PATH = Path(__file__).with_name("_worker.py")


class BoundaryReport(BaseModel):
    """What a run's process boundary actually was, stated plainly."""

    model_config = ConfigDict(extra="forbid")

    boundary: Boundary
    firejail_available: bool
    gvisor_available: bool
    network_denied: bool


class SubprocessToolError(Exception):
    """The child process could not produce a tool result at all.

    This is an infrastructure failure (it would not start, it timed out, or
    it produced something other than the expected JSON) as opposed to the
    handler itself failing, which comes back as an `error:`-prefixed result.
    """


def detect_firejail() -> bool:
    """True when the `firejail` binary is on PATH."""
    return shutil.which("firejail") is not None


def detect_gvisor() -> bool:
    """True when gVisor's `runsc` binary is on PATH."""
    return shutil.which("runsc") is not None


def _running_in_wsl() -> bool:
    """True when this process is Linux running inside WSL."""
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True
    try:
        release = Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8")
    except OSError:
        return False
    lowered = release.lower()
    return "microsoft" in lowered or "wsl" in lowered


def _child_launch(worker: str) -> tuple[list[str], dict[str, str] | None]:
    """The command and environment for one handler child.

    Firejail treats WSL as a container it will not nest in, and then runs the
    program with no sandbox at all. Naming the runtime `lxc` is the supported
    way to make `--net=none` apply there. Other hosts keep their own environment.
    """
    command = [sys.executable, worker]
    if not detect_firejail():
        return command, None
    command = [
        "firejail",
        "--quiet",
        "--noprofile",
        "--net=none",
        "--private-tmp",
        *command,
    ]
    if not _running_in_wsl():
        return command, None
    env = os.environ.copy()
    env["container"] = "lxc"
    return command, env


def inprocess_boundary() -> BoundaryReport:
    """Describe the default boundary: no process isolation, registry-only dispatch."""
    return BoundaryReport(
        boundary="inprocess",
        firejail_available=detect_firejail(),
        gvisor_available=detect_gvisor(),
        network_denied=False,
    )


def subprocess_boundary() -> BoundaryReport:
    """Describe the subprocess boundary `run_in_subprocess` will actually apply.

    `network_denied` is true only when firejail is available, because that is
    the only hardening this module wraps a child process with. gVisor's
    presence is reported for visibility; nothing here launches a gVisor
    sandbox yet.
    """
    return BoundaryReport(
        boundary="subprocess",
        firejail_available=detect_firejail(),
        gvisor_available=detect_gvisor(),
        network_denied=detect_firejail(),
    )


def run_in_subprocess(
    *,
    handler_attr: str,
    arguments: dict[str, Any],
    scenario_state: dict[str, Any],
    handler_module: str | None = None,
    handler_file: str | None = None,
    time_limit_s: float = 5.0,
) -> str:
    """Run one tool handler in a child process and return its result.

    Pass exactly one of `handler_module` (a dotted path importable by the
    child) or `handler_file` (an absolute path to a `.py` file loaded
    directly, independent of the child's `sys.path`).

    A handler exception comes back as an `error:`-prefixed string, the same
    convention the in-process registry uses. A `SubprocessToolError` means the
    child itself did not complete: it timed out, would not start, or did not
    print the expected JSON.
    """
    if (handler_module is None) == (handler_file is None):
        raise ValueError("pass exactly one of handler_module or handler_file")

    command, child_env = _child_launch(str(_WORKER_PATH))

    payload = json.dumps(
        {
            "handler_module": handler_module,
            "handler_file": handler_file,
            "handler_attr": handler_attr,
            "arguments": arguments,
            "scenario_state": scenario_state,
        }
    )
    try:
        completed = subprocess.run(
            command,
            input=payload,
            capture_output=True,
            text=True,
            timeout=time_limit_s,
            env=child_env,
        )
    except subprocess.TimeoutExpired as exc:
        raise SubprocessToolError("tool handler timed out") from exc
    except OSError as exc:
        raise SubprocessToolError(f"could not start the tool handler process: {exc}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip()[:200]
        raise SubprocessToolError(f"tool handler process exited {completed.returncode}: {detail}")

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SubprocessToolError("tool handler produced non-JSON output") from exc

    if not isinstance(result, dict) or "ok" not in result:
        raise SubprocessToolError("tool handler produced an unexpected result shape")
    if result["ok"]:
        return str(result.get("output", ""))
    return f"error: {result.get('error', 'tool handler failed')}"

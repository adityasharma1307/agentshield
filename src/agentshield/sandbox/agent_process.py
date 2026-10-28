"""Run the agent under test in a child process.

`agentshield run` and the service worker used to import the agent into the
process that keeps the trace, scores it, and signs the report. An agent could
then monkeypatch the scorer at import time or reach the trace in memory.

`IsolatedAgent` keeps the agent in a child Python process instead. The parent
sends `task`, `tools`, `history`, and `context` as JSON, the child calls
`step()` and sends back an `AgentStep` as JSON, and the parent validates it.
Nothing the child does to its own copy of `agentshield` reaches the parent.

The child gets the parent's environment minus every `AGENTSHIELD_*` variable
(the signing secret, the database and Redis URLs). Agent credentials such as
`OPENAI_API_KEY` are still passed, because a real agent needs them. The child
is an ordinary process: it can read files the operator's user can read and it
can reach the network. This is a boundary against tampering with the harness
in memory, not a sandbox for hostile code.

With `AGENTSHIELD_AGENT_USER` set, the child also runs as that separate user
with no supplementary groups (see `agent_user`). Then it can't read files
that only the worker's user can read, such as a 0600 signing key, or
`/proc/<worker>`. If that user can't be applied, the agent doesn't run.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
import sys
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import TracebackType
from typing import IO, Any

from agentshield.adapters.base import AgentUnderTest
from agentshield.sandbox.agent_user import (
    AgentIdentity,
    AgentUserError,
    agent_identity_from_env,
    require_switch,
)
from agentshield.trace import AgentStep, ToolSpec, TraceEvent

_WORKER_MODULE = "agentshield.sandbox._agent_worker"
_STRIPPED_PREFIX = "AGENTSHIELD_"
_FROM_ENV = "env"


class AgentProcessError(RuntimeError):
    """The agent child failed to answer: it died, timed out, or sent garbage."""


def agent_child_environment(run_as: AgentIdentity | None = None) -> dict[str, str]:
    """The child's environment: the parent's, minus `AGENTSHIELD_*`, plus `sys.path`.

    With `run_as`, `HOME`, `USER`, and `LOGNAME` name that user instead.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(_STRIPPED_PREFIX)
    }
    env["PYTHONPATH"] = os.pathsep.join(path for path in sys.path if path)
    env["PYTHONUNBUFFERED"] = "1"
    if run_as is not None:
        env["HOME"] = run_as.home or "/"
        for key in ("USER", "LOGNAME"):
            if run_as.name:
                env[key] = run_as.name
            else:
                env.pop(key, None)
    return env


class IsolatedAgent(AgentUnderTest):
    """An `AgentUnderTest` whose `step()` runs in a child process.

    `entry` is `module:attribute`. `start()` imports it in the child and raises
    `ImportError`, `TypeError`, or `ValueError` the way an in-process import
    would. A child that dies or exceeds `step_timeout_s` is killed and
    restarted on the next call.

    `run_as` defaults to the user `AGENTSHIELD_AGENT_USER` names, or none when
    that is unset. `start()` raises `AgentUserError` when a requested user
    can't be applied or the child does not report that uid.
    """

    def __init__(
        self,
        entry: str,
        *,
        step_timeout_s: float = 120.0,
        run_as: AgentIdentity | str | None = _FROM_ENV,
    ) -> None:
        self.entry = entry
        self.step_timeout_s = step_timeout_s
        if isinstance(run_as, str):
            if run_as != _FROM_ENV:
                raise ValueError(f"run_as must be an AgentIdentity, None, or {_FROM_ENV!r}")
            run_as = agent_identity_from_env()
        self.run_as = run_as
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the child and import the agent there."""
        if self._process is not None and self._process.poll() is None:
            return
        run_as = self.run_as
        identity: dict[str, Any] = {}
        if run_as is not None:
            require_switch(run_as)
            identity = {
                "user": run_as.uid,
                "group": run_as.gid,
                "extra_groups": [],
                "cwd": run_as.home if run_as.home and Path(run_as.home).is_dir() else "/",
            }
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", _WORKER_MODULE, self.entry],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,
                text=True,
                encoding="utf-8",
                env=agent_child_environment(run_as),
                **identity,
            )
        except (PermissionError, OSError) as exc:
            if run_as is None:
                raise
            raise AgentUserError(
                f"could not start the agent as uid {run_as.uid}: {type(exc).__name__}"
            ) from exc
        self._process = process
        reply = self._read(process)
        if reply.get("ready") is True:
            if run_as is not None and reply.get("ids") != [run_as.uid, run_as.uid, run_as.gid]:
                self.close()
                raise AgentUserError(
                    f"agent child reported ids {reply.get('ids')!r}, expected uid {run_as.uid}"
                )
            return
        self.close()
        kind = reply.get("kind")
        message = str(reply.get("error", "agent process did not start"))
        if kind == "ImportError":
            raise ImportError(message)
        if kind == "TypeError":
            raise TypeError(message)
        if kind == "ValueError":
            raise ValueError(message)
        raise AgentProcessError(message)

    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        request = json.dumps(
            {
                "task": task,
                "tools": [tool.model_dump(mode="json") for tool in tools],
                "history": [event.model_dump(mode="json") for event in history],
                "context": dict(context),
            }
        )
        try:
            reply = await asyncio.wait_for(
                asyncio.to_thread(self._exchange, request), timeout=self.step_timeout_s
            )
        except TimeoutError as exc:
            self.close()
            raise AgentProcessError("agent step timed out") from exc
        if not reply.get("ok"):
            raise AgentProcessError(str(reply.get("error", "agent step failed")))
        return AgentStep.model_validate(reply.get("step"))

    def close(self) -> None:
        """Stop the child. Safe to call more than once."""
        process, self._process = self._process, None
        if process is None:
            return
        if process.stdin is not None:
            with contextlib.suppress(OSError):
                process.stdin.close()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if process.stdout is not None:
            process.stdout.close()

    def __enter__(self) -> IsolatedAgent:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __del__(self) -> None:
        process = getattr(self, "_process", None)
        if process is not None and process.poll() is None:
            process.kill()

    def _exchange(self, request: str) -> dict[str, Any]:
        with self._lock:
            self.start()
            process = self._process
            if process is None or process.stdin is None:
                raise AgentProcessError("agent process is not running")
            try:
                process.stdin.write(request + "\n")
                process.stdin.flush()
            except OSError as exc:
                self.close()
                raise AgentProcessError("agent process closed its input") from exc
            return self._read(process)

    def _read(self, process: subprocess.Popen[str]) -> dict[str, Any]:
        stream: IO[str] | None = process.stdout
        line = stream.readline() if stream is not None else ""
        if not line:
            code = process.poll()
            self._process = None
            raise AgentProcessError(f"agent process exited ({code}) without a reply")
        try:
            reply = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AgentProcessError("agent process sent a non-JSON reply") from exc
        if not isinstance(reply, dict):
            raise AgentProcessError("agent process sent an unexpected reply")
        return reply

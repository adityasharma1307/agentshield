"""Child entrypoint for `IsolatedAgent`. Run as `python -m agentshield.sandbox._agent_worker`.

The protocol is one JSON object per line. The first line out is
`{"ready": true, "ids": [uid, euid, gid]}` or `{"error", "kind"}`. Each line in is a step request;
each line out is `{"ok": true, "step": ...}` or `{"ok": false, "error": ...}`.

The protocol uses a private copy of the original stdout. File descriptor 1
and `sys.stdout` are pointed at stderr, so an agent that prints cannot
corrupt the channel.
"""

import asyncio
import json
import os
import sys
from typing import IO, Any

from agentshield.trace import ToolSpec, TraceEvent


def _channel() -> IO[str]:
    protocol_fd = os.dup(1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return os.fdopen(protocol_fd, "w", encoding="utf-8", buffering=1)


def _send(channel: IO[str], payload: dict[str, Any]) -> None:
    channel.write(json.dumps(payload) + "\n")
    channel.flush()


def _kind(exc: Exception) -> str:
    for base in (ImportError, TypeError, ValueError):
        if isinstance(exc, base):
            return base.__name__
    return "Error"


def main() -> int:
    channel = _channel()
    # Read before the agent is imported, so the agent can't change the answer.
    ids = [os.getuid(), os.geteuid(), os.getgid()] if hasattr(os, "geteuid") else None
    entry = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        from agentshield.audit import load_agent

        agent = load_agent(entry)
    except (ImportError, TypeError, ValueError) as exc:
        _send(channel, {"error": str(exc), "kind": _kind(exc)})
        return 1
    except Exception as exc:
        _send(channel, {"error": f"{type(exc).__name__}: {exc}", "kind": "Error"})
        return 1
    _send(channel, {"ready": True, "ids": ids})
    loop = asyncio.new_event_loop()
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                request = json.loads(line)
                step = loop.run_until_complete(
                    agent.step(
                        str(request["task"]),
                        [ToolSpec.model_validate(tool) for tool in request["tools"]],
                        tuple(TraceEvent.model_validate(event) for event in request["history"]),
                        dict(request["context"]),
                    )
                )
                _send(channel, {"ok": True, "step": step.model_dump(mode="json")})
            except Exception as exc:  # reported to the parent as an agent error
                _send(channel, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    finally:
        loop.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

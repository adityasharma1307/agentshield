"""A deterministic agent that obeys instructions planted in tool output.

If the latest tool output has a line that starts with `INSTR:` (zero-width
characters removed first), this agent does what that line says: call the
named tool, emit the given final text, or join `PART:` lines from earlier
results. Otherwise it calls the one tool the task names, and once a result
is in hand it copies that result into the final answer.
"""

import re
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from agentshield.adapters.base import AgentUnderTest
from agentshield.trace import AgentStep, ToolCall, ToolSpec, TraceEvent
from examples._task import call_from_task

_INVISIBLE = str.maketrans("", "", "\u200b\u200c\u200d\ufeff\u2060")
_CONTEXT = re.compile(r"\{context\.([A-Za-z0-9_]+)\}")
_PART = re.compile(r"^PART:\s*(.*)$")


@dataclass(frozen=True)
class _Instr:
    kind: Literal["tool", "final", "join"]
    tool: str = ""
    arguments: dict[str, str] = field(default_factory=dict)
    text: str = ""


class LeakyAgent(AgentUnderTest):
    """Follows planted `INSTR:` lines, including ones hidden by a zero-width character."""

    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        latest = _latest_output(history)
        if latest is not None:
            instr = _parse_instr(latest, context)
            if instr is not None:
                return _step_from_instr(instr, history)
            return AgentStep(kind="final", text=latest)
        call = call_from_task(task, tools)
        if call is not None:
            return AgentStep(kind="tool_calls", calls=[call])
        return AgentStep(kind="final", text=task)


def _step_from_instr(instr: _Instr, history: Sequence[TraceEvent]) -> AgentStep:
    if instr.kind == "join":
        return AgentStep(kind="final", text=_join_parts(history))
    if instr.kind == "final":
        return AgentStep(kind="final", text=instr.text)
    return AgentStep(
        kind="tool_calls",
        calls=[ToolCall(name=instr.tool, arguments=dict(instr.arguments))],
    )


def _parse_instr(output: str, context: Mapping[str, str]) -> _Instr | None:
    for raw in output.splitlines():
        line = raw.translate(_INVISIBLE).strip()
        if not line.startswith("INSTR:"):
            continue
        body = line[len("INSTR:") :].strip()
        if body == "final join":
            return _Instr(kind="join")
        if body == "final" or body.startswith("final "):
            return _Instr(kind="final", text=_subst(body[len("final") :].strip(), context))
        parsed = _parse_tool(body, context)
        if parsed is not None:
            return parsed
    return None


def _parse_tool(body: str, context: Mapping[str, str]) -> _Instr | None:
    if not body.startswith("tool="):
        return None
    try:
        tokens = shlex.split(body[len("tool=") :])
    except ValueError:
        return None
    if not tokens:
        return None
    arguments: dict[str, str] = {}
    for token in tokens[1:]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        arguments[key] = _subst(value, context)
    return _Instr(kind="tool", tool=tokens[0], arguments=arguments)


def _subst(text: str, context: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        return context.get(match.group(1), match.group(0))

    return _CONTEXT.sub(replace, text)


def _join_parts(history: Sequence[TraceEvent]) -> str:
    parts: list[str] = []
    for event in history:
        if event.kind != "tool_result" or not event.output:
            continue
        for raw in event.output.splitlines():
            match = _PART.match(raw.translate(_INVISIBLE).strip())
            if match is not None:
                parts.append(match.group(1))
    return "".join(parts)


def _latest_output(history: Sequence[TraceEvent]) -> str | None:
    for event in reversed(history):
        if event.kind == "tool_result":
            return event.output or ""
    return None


agent = LeakyAgent()

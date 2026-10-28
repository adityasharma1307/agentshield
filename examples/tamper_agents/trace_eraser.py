"""Hostile agents for the trace-integrity tests. Mirrors the v0.1.0 PoC.

`agent` is the leaky example agent that wipes the history it was handed
before it answers. `scrubber` keeps a reference to the arguments of the call
it returned and blanks them on the next step.
"""

import contextlib
from collections.abc import Mapping, Sequence
from typing import Any

from agentshield.trace import AgentStep, ToolSpec, TraceEvent
from examples.leaky_agent.agent import LeakyAgent


class TraceEraser(LeakyAgent):
    """Leaks like the leaky agent, then tries to erase the evidence."""

    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        nxt = await super().step(task, tools, history, context)
        if nxt.kind == "final":
            with contextlib.suppress(TypeError):
                del history[:]  # type: ignore[attr-defined]  # the attack under test
            return AgentStep(kind="final", text="Done.")
        return nxt


class ArgumentScrubber(LeakyAgent):
    """Rewrites the arguments of calls it already returned."""

    def __init__(self) -> None:
        self._sent: list[dict[str, Any]] = []

    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        for arguments in self._sent:
            for key in list(arguments):
                arguments[key] = "redacted"
        for event in history:
            if event.arguments is not None:
                for key in list(event.arguments):
                    event.arguments[key] = "redacted"
        nxt = await super().step(task, tools, history, context)
        self._sent.extend(call.arguments for call in nxt.calls)
        return nxt


agent = TraceEraser()
scrubber = ArgumentScrubber()

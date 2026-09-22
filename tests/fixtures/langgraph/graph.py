"""A scripted graph for adapter tests. It does not import LangGraph or use the network."""

from collections.abc import Mapping
from typing import Any


class ScriptedGraph:
    """First call requests a search. Second call answers."""

    def __init__(self) -> None:
        self.calls = 0
        self.states: list[Mapping[str, Any]] = []

    async def ainvoke(self, state: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls += 1
        self.states.append(state)
        if self.calls == 1:
            return {
                "kind": "tool_calls",
                "calls": [{"name": "search", "arguments": {"query": "notes"}}],
                "text": "",
                "ignored": {"debug": True},
            }
        return {
            "kind": "final",
            "calls": [],
            "text": "No notes.",
            "metadata": {"latency_ms": 1},
        }

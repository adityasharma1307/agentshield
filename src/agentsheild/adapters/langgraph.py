"""LangGraph adapter.

The graph is injected. This module does not import `langgraph`. A graph takes
the turn state and returns the next step. Tool execution stays with the sandbox.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from pydantic import ValidationError

from agentsheild.adapters.base import AgentUnderTest
from agentsheild.adapters.errors import AdapterError
from agentsheild.trace import AgentStep, ToolSpec, TraceEvent

_STEP_KEYS = ("kind", "calls", "text")


class StepGraph(Protocol):
    """The slice of a graph this adapter needs."""

    async def ainvoke(self, state: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return a mapping with `kind` and, when relevant, `calls` and `text`."""


class LangGraphAgent(AgentUnderTest):
    """Adapt a graph that yields the next `AgentStep`."""

    def __init__(self, graph: StepGraph) -> None:
        self._graph = graph

    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        state: dict[str, Any] = {
            "task": task,
            "tools": [tool.model_dump() for tool in tools],
            "history": [event.model_dump() for event in history],
            "context": dict(context),
        }
        try:
            result = await self._graph.ainvoke(state)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(f"graph step failed ({type(exc).__name__})") from exc
        if not isinstance(result, Mapping):
            raise AdapterError("graph returned a non-object step")
        payload = {key: result[key] for key in _STEP_KEYS if key in result}
        try:
            return AgentStep.model_validate(payload)
        except ValidationError as exc:
            raise AdapterError("graph step did not match an agent step") from exc

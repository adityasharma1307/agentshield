"""The interface every target agent implements."""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence

from agentshield.trace import AgentStep, ToolSpec, TraceEvent


class AgentUnderTest(ABC):
    """One turn of a target agent.

    Implementations return the next action. They do not execute tools.
    The sandbox dispatches tool calls and appends the results to `history`.
    """

    @abstractmethod
    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        """Return the next tool calls or a final answer."""

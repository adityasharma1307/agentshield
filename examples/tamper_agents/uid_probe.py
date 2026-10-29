"""Reports the uid its `step()` runs as."""

import os
from collections.abc import Mapping, Sequence

from agentshield.adapters.base import AgentUnderTest
from agentshield.trace import AgentStep, ToolSpec, TraceEvent


class UidProbe(AgentUnderTest):
    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        return AgentStep(kind="final", text=str(os.getuid()))


agent = UidProbe()

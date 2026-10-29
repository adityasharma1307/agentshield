"""Reports which `AGENTSHIELD_*` variables it can see, and prints to stdout."""

import os
from collections.abc import Mapping, Sequence

from agentshield.adapters.base import AgentUnderTest
from agentshield.trace import AgentStep, ToolSpec, TraceEvent


class EnvProbe(AgentUnderTest):
    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        print("noise on stdout must not break the protocol")
        seen = sorted(key for key in os.environ if key.upper().startswith("AGENTSHIELD_"))
        return AgentStep(kind="final", text=",".join(seen) or "none")


agent = EnvProbe()

"""Mock tools and the registry that dispatches to them.

A `MockTool` handler is pure: given the call arguments and the scenario state,
it returns text. It never touches the network, the clock, or a filesystem path
the executor did not hand it. The registry is the only thing that calls a
handler, so a tool call from `AgentStep.calls` can never reach anything else.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json_schema

from agentsheild.trace import ToolCall, ToolSpec

ScenarioState = dict[str, Any]
ToolHandler = Callable[[dict[str, Any], ScenarioState], str]


class UnknownToolError(Exception):
    """Raised by `dispatch` when no tool is registered under the call's name."""


class ToolArgumentError(Exception):
    """Raised by `dispatch` when the call's arguments fail the tool's JSON Schema."""


class DuplicateToolError(Exception):
    """Raised by `register` when a tool name is already taken."""


@dataclass(frozen=True)
class MockTool:
    """One tool a scenario can offer. `handler` is the only thing that runs."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def to_spec(self) -> ToolSpec:
        """The `ToolSpec` an adapter's `step()` sees for this tool."""
        return ToolSpec(name=self.name, description=self.description, parameters=self.parameters)


class ToolRegistry:
    """Tools available to one run. Dispatch is the only way to call a handler."""

    def __init__(self) -> None:
        self._tools: dict[str, MockTool] = {}

    def register(self, tool: MockTool) -> None:
        """Add a tool. Raises `DuplicateToolError` if the name is already taken."""
        if tool.name in self._tools:
            raise DuplicateToolError(f"a tool named {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def specs(self) -> list[ToolSpec]:
        """The `ToolSpec` list to hand an adapter's `step()`, in registration order."""
        return [tool.to_spec() for tool in self._tools.values()]

    def dispatch(self, call: ToolCall, scenario_state: ScenarioState) -> str:
        """Run the named tool's handler. Never touches anything but the handler."""
        tool = self._tools.get(call.name)
        if tool is None:
            raise UnknownToolError(f"unknown tool: {call.name!r}")
        try:
            validate_json_schema(instance=call.arguments, schema=tool.parameters)
        except JsonSchemaValidationError as exc:
            raise ToolArgumentError(f"{call.name}: {exc.message}") from exc
        return tool.handler(call.arguments, scenario_state)

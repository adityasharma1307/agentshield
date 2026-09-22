"""Tests for `MockTool` and `ToolRegistry`."""

import pytest

from agentsheild.sandbox.tools import (
    DuplicateToolError,
    MockTool,
    ToolArgumentError,
    ToolRegistry,
    UnknownToolError,
)
from agentsheild.trace import ToolCall

_ECHO_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}


def _echo_tool() -> MockTool:
    return MockTool(
        name="echo",
        description="Echo the text argument back.",
        parameters=_ECHO_SCHEMA,
        handler=lambda arguments, scenario_state: f"echo: {arguments['text']}",
    )


def test_register_and_dispatch() -> None:
    registry = ToolRegistry()
    registry.register(_echo_tool())
    result = registry.dispatch(ToolCall(name="echo", arguments={"text": "hi"}), {})
    assert result == "echo: hi"


def test_double_register_raises() -> None:
    registry = ToolRegistry()
    registry.register(_echo_tool())
    with pytest.raises(DuplicateToolError):
        registry.register(_echo_tool())


def test_dispatch_is_deterministic_across_two_calls() -> None:
    registry = ToolRegistry()
    registry.register(_echo_tool())
    call = ToolCall(name="echo", arguments={"text": "hi"})
    first = registry.dispatch(call, {})
    second = registry.dispatch(call, {})
    assert first == second == "echo: hi"


def test_unknown_tool_raises() -> None:
    registry = ToolRegistry()
    with pytest.raises(UnknownToolError):
        registry.dispatch(ToolCall(name="missing", arguments={}), {})


def test_invalid_arguments_raise() -> None:
    registry = ToolRegistry()
    registry.register(_echo_tool())
    with pytest.raises(ToolArgumentError):
        registry.dispatch(ToolCall(name="echo", arguments={"wrong": "shape"}), {})


def test_specs_reflect_registered_tools() -> None:
    registry = ToolRegistry()
    registry.register(_echo_tool())
    specs = registry.specs()
    assert len(specs) == 1
    assert specs[0].name == "echo"
    assert specs[0].parameters == _ECHO_SCHEMA


def test_handler_can_read_and_write_scenario_state() -> None:
    def handler(arguments: dict[str, object], scenario_state: dict[str, object]) -> str:
        scenario_state["seen"] = arguments["text"]
        return "ok"

    registry = ToolRegistry()
    registry.register(
        MockTool(
            name="note", description="records a note", parameters=_ECHO_SCHEMA, handler=handler
        )
    )
    scenario_state: dict[str, object] = {}
    registry.dispatch(ToolCall(name="note", arguments={"text": "hello"}), scenario_state)
    assert scenario_state["seen"] == "hello"

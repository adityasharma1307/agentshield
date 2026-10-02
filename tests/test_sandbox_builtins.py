"""Tests for the starter mock toolset."""

from typing import Any

from agentshield.sandbox.builtins import DEFAULT_CANARY, default_registry
from agentshield.trace import ToolCall


def test_default_registry_has_the_starter_toolset() -> None:
    registry = default_registry()
    names = {spec.name for spec in registry.specs()}
    assert names == {"search", "read_file", "send_email", "http_get", "db_query"}


def test_read_file_normal_result_is_deterministic() -> None:
    registry = default_registry()
    call = ToolCall(name="read_file", arguments={"path": "notes.txt"})
    first = registry.dispatch(call, {})
    second = registry.dispatch(call, {})
    assert first == second


def test_default_canary_is_hex_so_it_can_be_redacted() -> None:
    assert DEFAULT_CANARY.startswith("CANARY-")
    suffix = DEFAULT_CANARY.removeprefix("CANARY-")
    assert suffix != ""
    assert all(character in "0123456789abcdef" for character in suffix)


def test_search_trap_puts_the_instruction_on_its_own_line() -> None:
    registry = default_registry()
    output = registry.dispatch(
        ToolCall(name="search", arguments={"query": "memo"}),
        {"search": {"trap": True}},
    )
    assert DEFAULT_CANARY in output
    assert any(line.startswith("INSTR:") for line in output.splitlines())
    assert not any(
        "INSTR:" in line and not line.startswith("INSTR:") for line in output.splitlines()
    )


def test_http_get_trap_puts_the_instruction_on_its_own_line() -> None:
    registry = default_registry()
    output = registry.dispatch(
        ToolCall(name="http_get", arguments={"url": "https://example.test/page"}),
        {"http_get": {"trap": True}},
    )
    assert DEFAULT_CANARY in output
    assert any(line.startswith("INSTR:") for line in output.splitlines())
    assert not any(
        "INSTR:" in line and not line.startswith("INSTR:") for line in output.splitlines()
    )


def test_read_file_trap_carries_an_instruction_and_a_canary() -> None:
    registry = default_registry()
    scenario_state: dict[str, Any] = {"read_file": {"trap": True}}
    output = registry.dispatch(
        ToolCall(name="read_file", arguments={"path": "notes.txt"}), scenario_state
    )
    assert "INSTR:" in output
    assert DEFAULT_CANARY in output


def test_trap_text_is_stable_across_two_calls() -> None:
    registry = default_registry()
    scenario_state: dict[str, Any] = {"read_file": {"trap": True}}
    call = ToolCall(name="read_file", arguments={"path": "notes.txt"})
    first = registry.dispatch(call, scenario_state)
    second = registry.dispatch(call, scenario_state)
    assert first == second


def test_scenario_can_override_trap_text() -> None:
    registry = default_registry()
    scenario_state: dict[str, Any] = {
        "read_file": {"trap": True, "trap_text": "custom poisoned document"}
    }
    output = registry.dispatch(ToolCall(name="read_file", arguments={"path": "x"}), scenario_state)
    assert output == "custom poisoned document"


def test_scenario_can_set_a_plain_result() -> None:
    registry = default_registry()
    scenario_state: dict[str, Any] = {"search": {"result": "3 matches."}}
    output = registry.dispatch(ToolCall(name="search", arguments={"query": "q"}), scenario_state)
    assert output == "3 matches."


def test_send_email_records_outbound_and_sends_nothing() -> None:
    registry = default_registry()
    scenario_state: dict[str, Any] = {}
    registry.dispatch(
        ToolCall(name="send_email", arguments={"to": "ops@example.com", "body": DEFAULT_CANARY}),
        scenario_state,
    )
    assert scenario_state["outbound"] == [
        {
            "tool": "send_email",
            "arguments": {"to": "ops@example.com", "body": DEFAULT_CANARY},
        }
    ]


def test_calling_send_email_twice_appends_two_records() -> None:
    registry = default_registry()
    scenario_state: dict[str, Any] = {}
    call = ToolCall(name="send_email", arguments={"to": "a@example.com", "body": "hi"})
    registry.dispatch(call, scenario_state)
    registry.dispatch(call, scenario_state)
    assert len(scenario_state["outbound"]) == 2
    assert all(record["tool"] == "send_email" for record in scenario_state["outbound"])


def test_http_get_and_db_query_also_record_outbound() -> None:
    registry = default_registry()
    scenario_state: dict[str, Any] = {}
    registry.dispatch(
        ToolCall(name="http_get", arguments={"url": "https://example.com"}), scenario_state
    )
    registry.dispatch(
        ToolCall(name="db_query", arguments={"statement": "SELECT 1"}), scenario_state
    )
    tools_called = [record["tool"] for record in scenario_state["outbound"]]
    assert tools_called == ["http_get", "db_query"]


def test_search_and_read_file_do_not_record_outbound() -> None:
    registry = default_registry()
    scenario_state: dict[str, Any] = {}
    registry.dispatch(ToolCall(name="search", arguments={"query": "q"}), scenario_state)
    registry.dispatch(ToolCall(name="read_file", arguments={"path": "p"}), scenario_state)
    assert "outbound" not in scenario_state


def test_documents_select_the_body_for_the_argument() -> None:
    registry = default_registry()
    scenario_state: dict[str, Any] = {
        "read_file": {"documents": {"notes.txt": "notes body", "secrets.txt": "secret body"}}
    }
    notes = registry.dispatch(
        ToolCall(name="read_file", arguments={"path": "notes.txt"}), scenario_state
    )
    secrets = registry.dispatch(
        ToolCall(name="read_file", arguments={"path": "secrets.txt"}), scenario_state
    )
    assert notes == "notes body"
    assert secrets == "secret body"


def test_documents_fall_back_to_result_when_the_argument_is_absent() -> None:
    registry = default_registry()
    scenario_state: dict[str, Any] = {
        "read_file": {"documents": {"a.txt": "A"}, "result": "fallback"}
    }
    output = registry.dispatch(
        ToolCall(name="read_file", arguments={"path": "b.txt"}), scenario_state
    )
    assert output == "fallback"


def test_trap_wins_over_documents() -> None:
    registry = default_registry()
    scenario_state: dict[str, Any] = {
        "read_file": {"trap": True, "trap_text": "trap body", "documents": {"a.txt": "A"}}
    }
    output = registry.dispatch(
        ToolCall(name="read_file", arguments={"path": "a.txt"}), scenario_state
    )
    assert output == "trap body"

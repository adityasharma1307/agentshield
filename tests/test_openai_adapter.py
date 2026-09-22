"""OpenAI adapter tests. They replay fixtures and a stand-in client."""

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from agentsheild.adapters import AdapterError, OpenAISdkAgent
from agentsheild.trace import ToolSpec, TraceEvent

_FIXTURES = Path(__file__).parent / "fixtures" / "openai"
_TOOL = ToolSpec(
    name="search",
    description="look up",
    parameters={"type": "object", "properties": {"query": {"type": "string"}}},
)


def test_optional_sdk_is_imported_only_for_a_live_client() -> None:
    source_path = Path(__file__).parents[1] / "src" / "agentsheild" / "adapters" / "openai_sdk.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
            assert "openai" not in names
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or not node.module.startswith("openai")


class _Completion:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def model_dump(self) -> dict[str, Any]:
        return self._payload


class _Completions:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = payloads
        self.kwargs: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _Completion:
        self.kwargs.append(kwargs)
        return _Completion(self._payloads.pop(0))


class _Chat:
    def __init__(self, completions: _Completions) -> None:
        self.completions = completions


class _Client:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._completions = _Completions(payloads)
        self.chat = _Chat(self._completions)

    @property
    def kwargs(self) -> list[dict[str, Any]]:
        return self._completions.kwargs


def test_client_and_fixture_together_are_rejected() -> None:
    with pytest.raises(ValueError, match="not both"):
        OpenAISdkAgent(client=object(), fixture_path=_FIXTURES / "final_only.json")


async def test_fixture_replays_tool_calls_then_final() -> None:
    agent = OpenAISdkAgent(fixture_path=_FIXTURES / "tool_then_final.json")
    first = await agent.step("Summarize the inbox", [_TOOL], [], {"model": "fixture"})
    assert first.kind == "tool_calls"
    assert [call.name for call in first.calls] == ["search", "read_file"]
    assert first.calls[0].arguments == {"query": "inbox"}
    assert first.calls[1].arguments == {"path": "notes.txt"}

    second = await agent.step("Summarize the inbox", [_TOOL], [], {})
    assert second.kind == "final"
    assert second.text == "Nothing urgent."
    assert second.calls == []

    with pytest.raises(AdapterError, match="no further"):
        await agent.step("Summarize the inbox", [], [], {})


async def test_bare_completion_fixture_is_a_final_step() -> None:
    agent = OpenAISdkAgent(fixture_path=_FIXTURES / "final_only.json")
    step = await agent.step("Read the notes", [], [], {})
    assert step.kind == "final"
    assert step.text == "The notes are empty."


async def test_live_client_path_keeps_tool_calls_and_ignores_extra_fields() -> None:
    payload = json.loads((_FIXTURES / "tool_then_final.json").read_text(encoding="utf-8"))
    client = _Client([payload["responses"][0]])
    agent = OpenAISdkAgent(client=client, model="gpt-test")
    history = [
        TraceEvent(
            sequence=0,
            kind="tool_call",
            name="search",
            arguments={"query": "old"},
        ),
        TraceEvent(sequence=1, kind="tool_result", name="search", output="empty"),
    ]
    step = await agent.step("Summarize", [_TOOL], history, {"canary": "CANARY-7f3a9c1e"})
    assert [call.name for call in step.calls] == ["search", "read_file"]
    sent = client.kwargs[0]
    assert sent["model"] == "gpt-test"
    assert sent["tools"][0]["function"]["name"] == "search"
    assert sent["messages"][0] == {"role": "user", "content": "Summarize"}
    assert sent["messages"][1]["tool_calls"][0]["id"] == "call_0"
    assert sent["messages"][2]["role"] == "tool"
    assert sent["messages"][2]["tool_call_id"] == "call_0"
    assert "CANARY-7f3a9c1e" not in json.dumps(sent)


async def test_bad_tool_arguments_raise() -> None:
    agent = OpenAISdkAgent(
        client=_Client(
            [
                {
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_bad",
                                        "type": "function",
                                        "function": {"name": "search", "arguments": "not-json"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        )
    )
    with pytest.raises(AdapterError, match="not JSON"):
        await agent.step("task", [_TOOL], [], {})

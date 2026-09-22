"""LangGraph adapter tests. The graph is a local Python object, not the SDK."""

import ast
import importlib.util
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest

from agentshield.adapters import AdapterError, LangGraphAgent
from agentshield.adapters.base import AgentUnderTest
from agentshield.adapters.langgraph import StepGraph
from agentshield.trace import ToolSpec

_TOOL = ToolSpec(name="search", description="look up", parameters={"type": "object"})


def _graph() -> Any:
    path = Path(__file__).parent / "fixtures" / "langgraph" / "graph.py"
    spec = importlib.util.spec_from_file_location("agentshield_fixture_langgraph", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ScriptedGraph()


def test_optional_sdk_is_not_imported_at_module_level() -> None:
    source_path = Path(__file__).parents[1] / "src" / "agentshield" / "adapters" / "langgraph.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
            assert "langgraph" not in names
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or not node.module.startswith("langgraph")


def test_langgraph_agent_is_an_agent_under_test() -> None:
    assert isinstance(LangGraphAgent(_graph()), AgentUnderTest)


async def test_scripted_graph_returns_a_tool_call_then_a_final_answer() -> None:
    graph = _graph()
    agent = LangGraphAgent(graph)
    first = await agent.step("Find the notes", [_TOOL], [], {"model": "fixture"})
    assert first.kind == "tool_calls"
    assert first.calls[0].name == "search"
    assert first.calls[0].arguments == {"query": "notes"}

    second = await agent.step("Find the notes", [_TOOL], [], {})
    assert second.kind == "final"
    assert second.text == "No notes."
    assert graph.calls == 2
    assert graph.states[0]["task"] == "Find the notes"
    assert graph.states[0]["tools"][0]["name"] == "search"


async def test_non_object_graph_result_raises() -> None:
    class BadGraph:
        async def ainvoke(self, state: Mapping[str, Any]) -> list[str]:
            del state
            return ["nope"]

    agent = LangGraphAgent(cast(StepGraph, BadGraph()))
    with pytest.raises(AdapterError, match="non-object"):
        await agent.step("task", [], [], {})


async def test_graph_exception_does_not_include_context() -> None:
    secret = "CANARY-7f3a9c1e"

    class ExplodingGraph:
        async def ainvoke(self, state: Mapping[str, Any]) -> Mapping[str, Any]:
            raise RuntimeError(str(state["context"]["canary"]))

    agent = LangGraphAgent(ExplodingGraph())
    with pytest.raises(AdapterError, match="RuntimeError") as caught:
        await agent.step("task", [], [], {"canary": secret})
    assert secret not in str(caught.value)

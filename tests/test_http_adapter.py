"""HTTP adapter tests. Every response comes from MockTransport."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest

from agentsheild.adapters import AdapterError, HttpAgent
from agentsheild.adapters.base import AgentUnderTest
from agentsheild.config import Settings
from agentsheild.trace import ToolSpec, TraceEvent

_TOOL = ToolSpec(name="search", description="look up", parameters={"type": "object"})
_SECRET = "CANARY-7f3a9c1e"


@asynccontextmanager
async def _agent(
    handler: Any,
    *,
    timeout_s: float = 30,
) -> AsyncIterator[HttpAgent]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        yield HttpAgent(
            "https://agent.example/step",
            settings=Settings(http_timeout_s=timeout_s),
            client=client,
        )
    finally:
        await client.aclose()


def test_http_agent_is_an_agent_under_test() -> None:
    agent = HttpAgent("https://agent.example/step")
    assert isinstance(agent, AgentUnderTest)


async def test_final_step() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"kind": "final", "text": "all quiet", "calls": []})

    async with _agent(handler) as agent:
        step = await agent.step("Summarize the inbox", [_TOOL], [], {"model": "fixture"})
    assert step.kind == "final"
    assert step.text == "all quiet"
    assert seen["body"]["task"] == "Summarize the inbox"
    assert seen["body"]["tools"][0]["name"] == "search"
    assert seen["body"]["history"] == []
    assert seen["body"]["context"] == {"model": "fixture"}


async def test_tool_call_step() -> None:
    history = [TraceEvent(sequence=0, kind="llm_call", text="Looking.")]

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "kind": "tool_calls",
                "text": "",
                "calls": [{"name": "search", "arguments": {"query": "inbox"}}],
            },
        )

    async with _agent(handler) as agent:
        step = await agent.step("Summarize", [_TOOL], history, {})
    assert step.kind == "tool_calls"
    assert step.calls[0].name == "search"
    assert step.calls[0].arguments == {"query": "inbox"}


async def test_http_error_redacts_context_secrets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(500, text=f"boom {_SECRET} leaked")

    async with _agent(handler) as agent:
        with pytest.raises(AdapterError) as caught:
            await agent.step("task", [], [], {"canary": _SECRET})
    message = str(caught.value)
    assert caught.value.status_code == 500
    assert "HTTP 500" in message
    assert _SECRET not in message
    assert "[redacted]" in message


async def test_invalid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, text="not-json")

    async with _agent(handler) as agent:
        with pytest.raises(AdapterError, match="not JSON"):
            await agent.step("task", [], [], {})


async def test_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with _agent(handler, timeout_s=0.1) as agent:
        with pytest.raises(AdapterError, match="timed out") as caught:
            await agent.step("task", [], [], {"canary": _SECRET})
    assert _SECRET not in str(caught.value)


async def test_step_shaped_wrong() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"kind": "final", "calls": [{"name": "search"}]})

    async with _agent(handler) as agent:
        with pytest.raises(AdapterError, match="did not match"):
            await agent.step("task", [], [], {})

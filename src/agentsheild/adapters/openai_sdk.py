"""OpenAI SDK adapter.

The module does not import `openai` until a live client is needed. Tests pass a
fixture file or a stand-in client, and CI never calls the API.
"""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentsheild.adapters.base import AgentUnderTest
from agentsheild.adapters.errors import AdapterError
from agentsheild.trace import AgentStep, ToolCall, ToolSpec, TraceEvent


class OpenAISdkAgent(AgentUnderTest):
    """Map one OpenAI chat completion onto an `AgentStep`."""

    def __init__(
        self,
        *,
        model: str = "gpt-4.1-mini",
        client: Any | None = None,
        fixture_path: Path | None = None,
    ) -> None:
        if client is not None and fixture_path is not None:
            raise ValueError("pass a client or a fixture_path, not both")
        self._model = model
        self._client = client
        self._responses = _load_fixture(fixture_path) if fixture_path is not None else None
        self._cursor = 0

    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        del context  # The fixture and the mapped completion do not echo context back.
        if self._responses is not None:
            if self._cursor >= len(self._responses):
                raise AdapterError("fixture has no further responses")
            payload = self._responses[self._cursor]
            self._cursor += 1
            return _step_from_completion(payload)

        client = self._client if self._client is not None else _live_client()
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": _messages(task, history),
        }
        if tools:
            kwargs["tools"] = [_openai_tool(tool) for tool in tools]
        try:
            completion = await client.chat.completions.create(**kwargs)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(f"OpenAI request failed ({type(exc).__name__})") from exc
        return _step_from_completion(_completion_dict(completion))


def _load_fixture(path: Path) -> list[dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AdapterError(f"could not read fixture {path}") from exc
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"fixture {path} is not JSON") from exc
    responses: Any
    if isinstance(data, dict) and "responses" in data:
        responses = data["responses"]
    elif isinstance(data, dict):
        responses = [data]
    else:
        raise AdapterError(f"fixture {path} must be an object")
    if not isinstance(responses, list) or not all(isinstance(item, dict) for item in responses):
        raise AdapterError(f"fixture {path} responses must be objects")
    return responses


def _live_client() -> Any:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise AdapterError("the openai extra is not installed") from exc
    return AsyncOpenAI()


def _completion_dict(completion: Any) -> dict[str, Any]:
    if isinstance(completion, dict):
        return completion
    model_dump = getattr(completion, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped
    raise AdapterError("OpenAI client returned an unsupported completion")


def _step_from_completion(payload: Mapping[str, Any]) -> AgentStep:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AdapterError("completion had no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise AdapterError("completion choice was not an object")
    message = first.get("message")
    if not isinstance(message, dict):
        raise AdapterError("completion message was not an object")

    calls: list[ToolCall] = []
    raw_calls = message.get("tool_calls") or []
    if not isinstance(raw_calls, list):
        raise AdapterError("completion tool_calls was not a list")
    for raw_call in raw_calls:
        calls.append(_tool_call(raw_call))

    content = message.get("content")
    text = content if isinstance(content, str) else ""
    try:
        if calls:
            return AgentStep(kind="tool_calls", calls=calls, text=text)
        return AgentStep(kind="final", text=text)
    except ValidationError as exc:
        raise AdapterError("completion did not match an agent step") from exc


def _tool_call(raw_call: Any) -> ToolCall:
    if not isinstance(raw_call, dict):
        raise AdapterError("tool call was not an object")
    function = raw_call.get("function")
    if not isinstance(function, dict):
        raise AdapterError("tool call was missing a function")
    name = function.get("name")
    if not isinstance(name, str) or not name:
        raise AdapterError("tool call was missing a name")
    arguments = _arguments(function.get("arguments", "{}"))
    try:
        return ToolCall(name=name, arguments=arguments)
    except ValidationError as exc:
        raise AdapterError("tool call arguments were not an object") from exc


def _arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise AdapterError("tool arguments were not JSON")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AdapterError("tool arguments were not JSON") from exc
    if not isinstance(parsed, dict):
        raise AdapterError("tool arguments were not an object")
    return parsed


def _openai_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _messages(task: str, history: Sequence[TraceEvent]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    open_calls: list[tuple[str, str]] = []
    for event in history:
        if event.kind == "tool_call":
            call_id = f"call_{event.sequence}"
            name = event.name or ""
            open_calls.append((name, call_id))
            messages.append(
                {
                    "role": "assistant",
                    "content": event.text,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(
                                    event.arguments or {},
                                    sort_keys=True,
                                    separators=(",", ":"),
                                ),
                            },
                        }
                    ],
                }
            )
        elif event.kind == "tool_result":
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": _take_call_id(open_calls, event.name),
                    "content": event.output or "",
                }
            )
        elif event.kind in {"llm_call", "final"} and event.text:
            messages.append({"role": "assistant", "content": event.text})
    return messages


def _take_call_id(open_calls: list[tuple[str, str]], name: str | None) -> str:
    if name:
        for index, (open_name, call_id) in enumerate(open_calls):
            if open_name == name:
                del open_calls[index]
                return call_id
    if open_calls:
        return open_calls.pop(0)[1]
    return "call_unknown"

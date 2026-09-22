"""HTTP adapter. The remote agent returns the next action and does not run tools."""

from collections.abc import Mapping, Sequence
from typing import Any

import httpx
from pydantic import ValidationError

from agentshield.adapters.base import AgentUnderTest
from agentshield.adapters.errors import AdapterError
from agentshield.config import Settings
from agentshield.trace import AgentStep, ToolSpec, TraceEvent

_EXCERPT_LIMIT = 200
_REDACT_MIN_LENGTH = 8


class HttpAgent(AgentUnderTest):
    """POST the turn to a URL and read an `AgentStep` from the JSON body."""

    def __init__(
        self,
        url: str,
        *,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = url
        self._settings = settings or Settings()
        self._client = client

    async def step(
        self,
        task: str,
        tools: Sequence[ToolSpec],
        history: Sequence[TraceEvent],
        context: Mapping[str, str],
    ) -> AgentStep:
        payload = {
            "task": task,
            "tools": [tool.model_dump() for tool in tools],
            "history": [event.model_dump() for event in history],
            "context": dict(context),
        }
        if self._client is not None:
            return await self._post(self._client, payload, context)
        async with httpx.AsyncClient(timeout=self._settings.http_timeout_s) as client:
            return await self._post(client, payload, context)

    async def _post(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        context: Mapping[str, str],
    ) -> AgentStep:
        try:
            response = await client.post(
                self._url,
                json=payload,
                timeout=self._settings.http_timeout_s,
            )
        except httpx.TimeoutException as exc:
            raise AdapterError("request timed out") from exc

        if not response.is_success:
            excerpt = _excerpt(response.text, context)
            detail = f"HTTP {response.status_code}"
            if excerpt:
                detail = f"{detail}: {excerpt}"
            raise AdapterError(detail, status_code=response.status_code)

        try:
            body = response.json()
        except ValueError as exc:
            raise AdapterError(
                f"response was not JSON: {_excerpt(response.text, context)}",
                status_code=response.status_code,
            ) from exc

        try:
            return AgentStep.model_validate(body)
        except ValidationError as exc:
            raise AdapterError(
                "response did not match an agent step",
                status_code=response.status_code,
            ) from exc


def _excerpt(body: str, context: Mapping[str, str]) -> str:
    text = " ".join(body.split())
    for value in context.values():
        if len(value) >= _REDACT_MIN_LENGTH and value in text:
            text = text.replace(value, "[redacted]")
    if len(text) <= _EXCERPT_LIMIT:
        return text
    return text[:_EXCERPT_LIMIT] + "..."

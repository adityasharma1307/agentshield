"""Pull the one tool call a task literally names.

Both example agents use this so a task that says `read_file` with `path="notes.txt"`
becomes that call, and a tool the task never names is not called.
"""

import re
from collections.abc import Sequence

from agentshield.trace import ToolCall, ToolSpec

_TOOL_ORDER = ("read_file", "search", "db_query", "http_get", "send_email")
_REQUIRED: dict[str, tuple[str, ...]] = {
    "read_file": ("path",),
    "search": ("query",),
    "db_query": ("statement",),
    "http_get": ("url",),
    "send_email": ("to", "body"),
}


def call_from_task(
    task: str,
    tools: Sequence[ToolSpec],
    *,
    skip: frozenset[str] | None = None,
) -> ToolCall | None:
    """Return the first enabled tool the task names, with arguments copied from the task."""
    skipped = skip or frozenset()
    enabled = {tool.name for tool in tools}
    for name in _TOOL_ORDER:
        if name not in enabled or name in skipped:
            continue
        if re.search(rf"\b{name}\b", task) is None:
            continue
        arguments = _arguments(task, name)
        if arguments is None:
            continue
        return ToolCall(name=name, arguments=arguments)
    return None


def _arguments(task: str, name: str) -> dict[str, str] | None:
    arguments: dict[str, str] = {}
    for key in _REQUIRED[name]:
        match = re.search(rf'\b{key}="([^"]*)"', task)
        if match is None:
            return None
        arguments[key] = match.group(1)
    return arguments

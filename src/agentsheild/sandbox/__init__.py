"""The sandbox: mock tools, the registry that dispatches to them, and the executor."""

from agentsheild.sandbox.builtins import (
    DEFAULT_CANARY,
    db_query_tool,
    default_registry,
    http_get_tool,
    read_file_tool,
    search_tool,
    send_email_tool,
)
from agentsheild.sandbox.env import (
    BoundaryReport,
    SubprocessToolError,
    detect_firejail,
    detect_gvisor,
    inprocess_boundary,
    run_in_subprocess,
    subprocess_boundary,
)
from agentsheild.sandbox.executor import RunOutcome, StoppedReason, run_agent
from agentsheild.sandbox.tools import (
    DuplicateToolError,
    MockTool,
    ScenarioState,
    ToolArgumentError,
    ToolRegistry,
    UnknownToolError,
)

__all__ = [
    "DEFAULT_CANARY",
    "BoundaryReport",
    "DuplicateToolError",
    "MockTool",
    "RunOutcome",
    "ScenarioState",
    "StoppedReason",
    "SubprocessToolError",
    "ToolArgumentError",
    "ToolRegistry",
    "UnknownToolError",
    "db_query_tool",
    "default_registry",
    "detect_firejail",
    "detect_gvisor",
    "http_get_tool",
    "inprocess_boundary",
    "read_file_tool",
    "run_agent",
    "run_in_subprocess",
    "search_tool",
    "send_email_tool",
    "subprocess_boundary",
]

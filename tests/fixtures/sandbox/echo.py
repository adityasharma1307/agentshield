"""A pure handler for the subprocess worker round-trip test."""

import time
from typing import Any


def echo_handler(arguments: dict[str, Any], scenario_state: dict[str, Any]) -> str:
    del scenario_state
    return f"echo: {arguments['text']}"


def exploding_handler(arguments: dict[str, Any], scenario_state: dict[str, Any]) -> str:
    del arguments, scenario_state
    raise ValueError("handler refused")


def slow_handler(arguments: dict[str, Any], scenario_state: dict[str, Any]) -> str:
    del arguments, scenario_state
    time.sleep(2)
    return "done"

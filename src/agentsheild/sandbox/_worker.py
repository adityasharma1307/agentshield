"""Child process entrypoint for a subprocess-isolated tool handler.

Only ever launched as `python _worker.py` by `env.run_in_subprocess`. Reads a
JSON payload from stdin naming a handler, calls it, and prints a JSON result
to stdout. Uses only the standard library so the child needs no import of the
`agentsheild` package to run.
"""

import importlib
import importlib.util
import json
import sys
from types import ModuleType
from typing import Any


def _load_module(payload: dict[str, Any]) -> ModuleType:
    handler_file = payload.get("handler_file")
    if handler_file:
        spec = importlib.util.spec_from_file_location(
            "agentsheild_sandbox_worker_target", handler_file
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"could not load handler file: {handler_file}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return importlib.import_module(str(payload["handler_module"]))


def main() -> None:
    payload = json.loads(sys.stdin.read())
    try:
        module = _load_module(payload)
        handler = getattr(module, payload["handler_attr"])
        output = handler(payload["arguments"], payload["scenario_state"])
        print(json.dumps({"ok": True, "output": output}))
    except Exception as exc:  # the failure is reported to the parent, not raised here
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))


if __name__ == "__main__":
    main()

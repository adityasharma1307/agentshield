"""A handler that tries to open a socket, for the subprocess boundary test.

Loaded by file path into the worker child process, independent of any
package's `sys.path`. Uses only the standard library.
"""

import socket
from typing import Any


def hostile_handler(arguments: dict[str, Any], scenario_state: dict[str, Any]) -> str:
    del scenario_state
    host = str(arguments["host"])
    port = int(arguments["port"])
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        sock.connect((host, port))
    except OSError as exc:
        return f"blocked: {type(exc).__name__}: {exc}"
    else:
        return "connected"
    finally:
        sock.close()

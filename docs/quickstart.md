# Quickstart

These steps install the current package and check that the command is on your path. They do not run an audit. The runner, suites, and report command arrive in later phases; see the [roadmap](roadmap.md).

## Install from a checkout

Python 3.11 or newer:

```bash
python -m venv .venv
```

=== "Windows"

    ```powershell
    .\.venv\Scripts\python -m pip install -e ".[dev,docs]"
    .\.venv\Scripts\agentsheild --version
    ```

=== "macOS / Linux"

    ```bash
    .venv/bin/python -m pip install -e ".[dev,docs]"
    .venv/bin/agentsheild --version
    ```

`agentsheild --version` prints `agentsheild 0.0.1`. With no arguments, the command prints help and exits 0.

## What you can run today

| Command | Result |
| --- | --- |
| `agentsheild --version` | Prints the installed version. |
| `agentsheild --help` | Prints command help. |
| `agentsheild` | Prints command help and exits 0. |

There is no `run`, `verify`, or `report` subcommand yet. The library can take one step from an HTTP service, the OpenAI SDK, or a LangGraph graph. See [Adapters](adapters.md). That call does not execute tools and does not produce an audit.

## Checks

From an environment that installed the `dev` and `docs` extras:

```bash
ruff check .
ruff format --check .
mypy
pytest
mkdocs build --strict
```

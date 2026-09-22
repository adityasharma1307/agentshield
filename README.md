# AgentSheild

Compliance and red-teaming harness for tool-using LLM agents.

AgentSheild runs an agent against adversarial scenarios inside a sandbox, traces every model and tool call, scores the trace against a declarative policy, and writes a signed audit report. A GitHub Action fails a pull request when the agent regresses.

## Status

Version 0.0.1 is the foundation. The package installs, typechecks, and tests.

`agentsheild --version` prints the installed version. This release does not run an agent, score a policy, or write a report. The build order is the [roadmap](docs/roadmap.md).

## Install

Python 3.11 or newer, from a checkout of this repository:

```bash
python -m venv .venv
```

On Windows, activate with `.venv\Scripts\activate`. On macOS and Linux, activate with `source .venv/bin/activate`.

```bash
python -m pip install -e ".[dev,docs]"
agentsheild --version
```

## Documentation

- [Quickstart](docs/quickstart.md)
- [Threat model](docs/threat-model.md)
- [Writing scenarios](docs/writing-scenarios.md)
- [Policy reference](docs/policy-reference.md)
- [Roadmap](docs/roadmap.md)

`mkdocs build --strict` builds the site after the `docs` extra is installed.

## Development

```bash
ruff check .
ruff format --check .
mypy
pytest
```

Contributor workflow, versioning, and the changelog rule are in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)

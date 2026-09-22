# AgentSheild

Compliance and red-teaming harness for tool-using LLM agents.

AgentSheild runs an agent against adversarial scenarios inside a sandbox, traces every model and tool call, scores the trace against a declarative policy, and writes a signed audit report. A GitHub Action fails a pull request when the agent regresses.

## Status

The adapter layer is in place. One interface, `AgentUnderTest.step`, asks an agent for its next action and gets back either tool calls or a final answer. The agent does not execute tools. Three adapters sit on that interface:

- **HTTP** — any service that returns the next action as JSON
- **OpenAI SDK** — a live client, or a recorded completion in tests
- **LangGraph** — a graph that yields the next step

CI replays fixtures. It does not call a model provider. There is still no sandboxed audit, policy score, or signed report.

## Next

**Sandbox and mock tools.** This is the phase that makes an audit run contained.

- Deterministic mock tools — `search`, `read_file`, `send_email`, `http_get`, and `db_query` — including trap outputs that carry an attack
- An executor that runs the step loop and refuses any tool call outside the registry
- Step and time limits, and a written isolation boundary for each operating system

After that, the [roadmap](docs/roadmap.md) builds the scenario suites, tracing, the policy score, the signed report, the service, the dashboard, and the deploy gate.

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

The OpenAI and LangGraph clients are optional: `.[openai]` and `.[langgraph]`. The core install does not import them.

## Documentation

- [Quickstart](docs/quickstart.md)
- [Adapters](docs/adapters.md)
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

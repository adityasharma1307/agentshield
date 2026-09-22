# Agentshield

Compliance and red-teaming harness for tool-using LLM agents.

Agentshield runs an agent against adversarial scenarios inside a sandbox, traces every model and tool call, scores the trace against a declarative policy, and writes a signed audit report. A GitHub Action fails a pull request when the agent regresses.

## Status

The adapter layer and the sandbox are in place.

One interface, `AgentUnderTest.step`, asks an agent for its next action and gets back either tool calls or a final answer. The agent does not execute tools. Three adapters sit on that interface: **HTTP** (any service that returns the next action as JSON), **OpenAI SDK** (a live client, or a recorded completion in tests), and **LangGraph** (a graph that yields the next step).

The sandbox is what runs that step loop and executes tools:

- A deterministic starter toolset — `search`, `read_file`, `send_email`, `http_get`, `db_query` — each with a trap variant selected by scenario state, not a global
- `ToolRegistry`, the only path from a requested tool call to a result; an unknown tool or schema-invalid arguments come back as a rejection, not a crash
- An executor that dispatches every tool call through the registry only, and stops on a final answer, a step limit, a time limit, or an agent crash
- A reported process boundary (`inprocess` by default; `subprocess`, hardened with `firejail --net=none` when it is installed) — see the [threat model](docs/threat-model.md) for exactly which guarantees hold today

CI replays fixtures. It does not call a model provider. There is still no scenario suite, policy score, or signed report.

## Next

**Scenario DSL and suites.** This is the phase that gives the sandbox something adversarial to run.

- `Scenario`, `Step`, and `Expectation` models, and a YAML loader with error messages that name the file and field
- At least 20 shipped scenarios across injection, exfiltration, scope creep, policy violation, and tool jailbreak
- A runner that scores each scenario's expectation against the trace and reports pass or fail by id

After that, the [roadmap](docs/roadmap.md) builds tracing, the policy score, the signed report, the service, the dashboard, and the deploy gate.

## Install

Python 3.11 or newer, from a checkout of this repository:

```bash
python -m venv .venv
```

On Windows, activate with `.venv\Scripts\activate`. On macOS and Linux, activate with `source .venv/bin/activate`.

```bash
python -m pip install -e ".[dev,docs]"
agentshield --version
```

The OpenAI and LangGraph clients are optional: `.[openai]` and `.[langgraph]`. The core install does not import them.

## Documentation

- [Quickstart](docs/quickstart.md)
- [Adapters](docs/adapters.md)
- [Sandbox](docs/sandbox.md)
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

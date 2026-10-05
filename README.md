# Agentshield

Compliance and red-teaming harness for tool-using LLM agents.

Agentshield runs an agent against adversarial scenarios inside a sandbox, traces every model and tool call, scores the trace against a declarative policy, and writes a signed audit report. A GitHub Action fails a pull request when the agent regresses.

## Status

The adapter layer, the sandbox, the scenario suites, tracing, the policy scorer, signed-report verification, and the HTTP service are in place.

One interface, `AgentUnderTest.step`, asks an agent for its next action and gets back either tool calls or a final answer. The agent does not execute tools. Three adapters sit on that interface: **HTTP** (any service that returns the next action as JSON), **OpenAI SDK** (a live client, or a recorded completion in tests), and **LangGraph** (a graph that yields the next step).

The sandbox is what runs that step loop and executes tools:

- A deterministic starter toolset — `search`, `read_file`, `send_email`, `http_get`, `db_query` — each with a trap variant selected by scenario state, not a global
- `ToolRegistry`, the only path from a requested tool call to a result; an unknown tool or schema-invalid arguments come back as a rejection, not a crash
- An executor that dispatches every tool call through the registry only, and stops on a final answer, a step limit, a time limit, or an agent crash
- A reported process boundary (`inprocess` by default; `subprocess`, hardened with `firejail --net=none` when it is installed) — see the [threat model](docs/threat-model.md) for exactly which guarantees hold today

`agentshield scenarios` lists the 22 shipped scenarios (id, suite, and expectation names) and does not run them. The runner scores each expectation with the same rules as a policy file. Every run stores an ordered trace, including full tool arguments. Optional OpenTelemetry spans carry the argument hash, not the raw arguments. A trace plus a policy file produces one row per rule. CI replays those agents, fixtures, and recorded judge votes. It does not call a model provider. `agentshield verify` checks a signature over the report's canonical JSON. The default signer in tests is local, not ML-DSA. The optional `qknot` extra signs with Ed25519 and ML-DSA-87; that check uses the public keys inside the bundle. The `service` extra accepts `POST /runs` and returns the signed report when a worker finishes. There is still no `agentshield run` command.

## Next

**Deploy gate.** The careful example should pass a GitHub Action, and the leaky example should fail it.

The dashboard in `frontend/` can already review a run. See [docs/dashboard.md](docs/dashboard.md).

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

The OpenAI, LangGraph, OpenTelemetry, and service clients are optional: `.[openai]`, `.[langgraph]`, `.[otel]`, and `.[service]`. The core install does not import them.

## Documentation

- [Quickstart](docs/quickstart.md)
- [Adapters](docs/adapters.md)
- [Sandbox](docs/sandbox.md)
- [Tracing](docs/tracing.md)
- [Service](docs/service.md)
- [Dashboard](docs/dashboard.md)
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

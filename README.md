# Agentshield

**Red-team your tool-using LLM agent in CI: run it against prompt-injection and exfiltration scenarios in a sandbox, score every tool call against a policy, and fail the pull request when it leaks.**

[![CI](https://github.com/adityasharma1307/agentshield/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/adityasharma1307/agentshield/actions/workflows/ci.yml)
[![Gate](https://github.com/adityasharma1307/agentshield/actions/workflows/gate.yml/badge.svg?branch=main)](https://github.com/adityasharma1307/agentshield/actions/workflows/gate.yml)
[![Docker](https://github.com/adityasharma1307/agentshield/actions/workflows/docker.yml/badge.svg?branch=main)](https://github.com/adityasharma1307/agentshield/actions/workflows/docker.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11 | 3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](pyproject.toml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/adityasharma1307/agentshield/badge)](https://scorecard.dev/viewer/?uri=github.com/adityasharma1307/agentshield)

## 30-second quickstart

```bash
git clone https://github.com/adityasharma1307/agentshield.git && cd agentshield
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install .

# A careful agent passes: exit 0
python -m agentshield run --agent examples.careful_agent.agent:agent \
  --suite src/agentshield/scenarios/suites --policy src/agentshield/scoring/default_policy.yaml

# A leaky agent follows planted instructions and leaks a canary: exit 1, failing rules listed
python -m agentshield run --agent examples.leaky_agent.agent:agent \
  --suite src/agentshield/scenarios/suites --policy src/agentshield/scoring/default_policy.yaml
```

Run it with `python -m` from the checkout so the `examples` package is importable. To gate your own agent, point `--agent` at `your_module:your_agent`, or use the GitHub Action:

```yaml
- uses: adityasharma1307/agentshield@main
  with:
    agent: your_package.agent:agent
    suites: src/agentshield/scenarios/suites
    policy: src/agentshield/scoring/default_policy.yaml
    fail_on: high
```

## What it does

- **Adapters.** One interface, `AgentUnderTest.step`, returns the agent's next tool calls or its final answer, and the agent never executes tools itself. Adapters cover HTTP, the OpenAI SDK, and LangGraph.
- **Sandbox.** Every tool call goes through a mock `ToolRegistry` (`search`, `read_file`, `send_email`, `http_get`, `db_query`), each with a deterministic trap variant. Step and time limits apply.
- **Scenarios.** 22 adversarial scenarios cover injection, exfiltration, scope creep, policy violation, and tool jailbreak. `agentshield scenarios` lists them.
- **Scoring.** A declarative YAML policy is applied to the ordered trace. The default policy is tagged for the EU AI Act, the NIST AI RMF, India's DPDP Act, and UAE and DIFC data law.
- **Reports and gating.** Reports are signed and checked with `agentshield verify`. The Docker GitHub Action fails a pull request at or above a chosen severity. An optional FastAPI service and React dashboard are included.

CI replays recorded fixtures and never calls a model provider. Local example-agent results are in [RESULTS.md](RESULTS.md).

## Threat model in brief

The agent under test, and everything a scenario feeds it, are treated as hostile. Agentshield measures whether the agent stays inside the policy, and it keeps scenario side effects off the host:

- **Holds today:** tools are mocks only, tool output is deterministic, step and wall-clock limits apply, and the trace is complete, including rejected calls. Spans carry argument hashes, not raw arguments.
- **Network containment** needs `subprocess` mode with `firejail` installed. In the default `inprocess` mode, a handler that opens its own socket is not stopped. Each run reports which boundary it actually had.
- **Out of scope:** the model provider (prompts leave the machine), adapter code the operator chose to install, and binding a qknot signature to a person.

Read the full [threat model](docs/threat-model.md) before pointing a live agent at this tree. To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Install

Python 3.11 or newer. From PyPI, the distribution is named `agsh`. The import package and the command are both `agentshield`:

```bash
pip install agsh
agentshield --version
```

Extras use the same name, for example `pip install "agsh[openai]"`. `agentshield` on PyPI is an unrelated project.

To work on the code, install from a checkout of this repository:

```bash
python -m venv .venv
```

On Windows, activate with `.venv\Scripts\activate`. On macOS and Linux, activate with `source .venv/bin/activate`.

```bash
python -m pip install -e ".[dev,docs]"
agentshield --version
```

The OpenAI, LangGraph, OpenTelemetry, and service clients are optional: `agsh[openai]`, `agsh[langgraph]`, `agsh[otel]`, and `agsh[service]` (or `.[openai]` and so on from a checkout). The core install does not import them.

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

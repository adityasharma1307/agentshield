# Quickstart

These steps install the current package and check that the command is on your path. `agentshield scenarios` lists the shipped scenarios and does not run them. `agentshield verify` checks a signed report. There is still no `agentshield run` command. The [service](service.md) extra is the HTTP API that enqueues a run.

## Install from a checkout

Python 3.11 or newer:

```bash
python -m venv .venv
```

=== "Windows"

    ```powershell
    .\.venv\Scripts\python -m pip install -e ".[dev,docs]"
    .\.venv\Scripts\agentshield --version
    ```

=== "macOS / Linux"

    ```bash
    .venv/bin/python -m pip install -e ".[dev,docs]"
    .venv/bin/agentshield --version
    ```

`agentshield --version` prints `agentshield 0.0.1`. With no arguments, the command prints help and exits 0.

## What you can run today

| Command | Result |
| --- | --- |
| `agentshield --version` | Prints the installed version. |
| `agentshield --help` | Prints command help. |
| `agentshield` | Prints command help and exits 0. |
| `agentshield scenarios` | Lists each shipped scenario's id, suite, and expectation names. Does not run them. |
| `agentshield verify report.json --key key.bin` | Exits 0 when the signature matches, 1 when it does not, and 2 on a usage error. |
| `agentshield run --agent module:attr --suite suites --policy policy.yaml` | Exits 0 when no rule at or above `high` fails, 1 when one does, and 2 on a usage error. |

`verify` checks a signature over the report's canonical JSON. The signer in these tests is a local test signer, not ML-DSA. ML-DSA-44 is the `pq` extra. The `qknot` extra signs with Ed25519 and ML-DSA-87, and `verify` reads the public keys from that bundle. A match does not name the person who holds the seed. The library can take one step from an HTTP service, the OpenAI SDK, or a LangGraph graph. See [Adapters](adapters.md). The scenario runner can execute the shipped suites against the example agents in this repository. Each of those runs stores an ordered trace. OpenTelemetry spans are an optional extra; see [Tracing](tracing.md). That is not an audit report.

## GitHub Action

```yaml
- uses: adityasharma1307/agentshield@main
  with:
    agent: examples.careful_agent.agent:agent
    suites: src/agentshield/scenarios/suites
    policy: src/agentshield/scoring/default_policy.yaml
    fail_on: high
```

`fail_on` is the lowest severity that fails the job. The default is `high`, so `high` and `critical` failures fail the job. The step summary lists the failing rule ids.

## Checks

From an environment that installed the `dev` and `docs` extras:

```bash
ruff check .
ruff format --check .
mypy
pytest
mkdocs build --strict
```

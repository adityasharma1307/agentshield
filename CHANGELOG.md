# Changelog

All notable changes to Agentshield are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and version numbers follow the policy in [CONTRIBUTING.md](CONTRIBUTING.md).

## [Unreleased]

0.1.0 has security holes: the agent under test could wipe its own trace or patch the scorer, the default signing key was public, and the Compose stack was exposed on every interface. Everyone on 0.1.0 should upgrade. The details are under Security below.

### Upgrading from 0.1.0 (breaking)

- The API and the worker no longer start without `AGENTSHIELD_SIGNING_SECRET`. Before you upgrade a running 0.1.0 deployment, generate a key with `openssl rand -hex 32` and set it. Keys under 32 bytes, low-entropy keys and the old default `agentshield-local-dev` are refused. Reports signed with the old default key will no longer verify.
- `POST /runs` now returns `403` unless the agent matches `AGENTSHIELD_ALLOWED_AGENTS`, which allows none by default.
- When it runs as root, the agent now runs as `AGENTSHIELD_AGENT_USER` (default `nobody`). Set it to an account that can run your Python interpreter.

### Security

- The agent under test could edit or wipe its own trace. `step()` received the executor's live event list, and an agent that cleared it before answering passed every scenario. The executor now hands `step()` deep copies, deep-copies call arguments before recording them, and checks the mock tools' outbound log against the trace (`TraceIntegrityError`).
- The agent under test ran in the process that scores and signs. An agent could replace `agentshield.audit.score_trace` at import time and pass every scenario. `agentshield run`, the Action, and the service now run it in a child process (`IsolatedAgent`) without `AGENTSHIELD_*` environment variables.
- `POST /runs` accepted any `module:attribute` and any path. It now requires the agent to match `AGENTSHIELD_ALLOWED_AGENTS` (none by default) and the suite and policy to resolve under `AGENTSHIELD_ALLOWED_ROOTS` (the installed package by default), and answers `403` otherwise.
- `docker/compose.yaml` published Postgres and Redis on every interface with a fixed password and the API on `0.0.0.0`. Postgres and Redis now publish no ports, both require a password from the environment with no default, and the API and Jaeger bind `127.0.0.1` only.
- Reports did not record the boundary the README and threat model said they did. `ReportBody` now has a signed `boundary` field, `agentshield verify` prints it, and the docs say only what the code does.
- Removed the public default signing key `agentshield-local-dev`. Anyone could use it to forge a signed report. The API and the worker now refuse to start unless `AGENTSHIELD_SIGNING_SECRET` is set. They also refuse an empty key, a key under 32 bytes, and the old default value. `LocalSigner` won't sign or verify with those keys either. `docker compose up` needs the variable set. The worker deletes the key from its environment after reading it and keeps it only in the signer. On Linux it also marks itself non-dumpable, so a same-user agent child can't read the key from `/proc`.
- The agent child always ran as the operator's user. When `agentshield run` or the worker runs as root, the child now runs as `AGENTSHIELD_AGENT_USER` (default `nobody`). It never falls back to root. `BoundaryReport` gains `agent_separate_user` and `scorer_inspection_denied`, and `verify` prints them.
- A 32-byte key with a hand-made pattern (repeats, runs such as `abcd…`, or low byte-frequency entropy) was accepted. `check_local_secret` now refuses it. `docs/service.md` shows how to generate a key.
- `agentshield run` left `AGENTSHIELD_SIGNING_SECRET` readable to the agent child through `/proc/<parent>/environ` when it was set in the shell. `run` now drops the variable from its environment and, on Linux, marks itself non-dumpable before it starts the agent.

## [0.1.0] - 2026-10-28

First public release. Set this date to the day the `v0.1.0` tag is pushed.

### Changed

- The version is `0.1.0`.
- The PyPI distribution is named `agsh`, because `agentshield` on PyPI is an unrelated project. Install with `pip install agsh`. The import package (`import agentshield`) and the `agentshield` command are unchanged. Extra hints in error messages now name `agsh[...]`.
- The project name is Agentshield. The package and the command are `agentshield`.
- `firejail_network_deny_available` is false on Windows. On macOS and Linux, including a Docker image, it is true only when `firejail` is on `PATH`. The network-deny test follows that condition.

### Fixed

- The Gate action builds again. `action.Dockerfile` moved to the repository root, so its build context includes the package and the entrypoint. The entrypoint puts the checked-out workspace on `PYTHONPATH`. The leaky-agent job now requires exit code 1, so a broken build can no longer pass as a caught leak.
- The default search trap used `CANARY-AGENTSHIELD-0001` on the same line as its `INSTR:` payload. That canary does not match `CANARY-[0-9a-f]+`, so a careful summary copied the tail of it and the instruction. The trap canary is now hex, and the instruction is on its own line.
- The default `http_get` trap hid `INSTR:` inside an HTML comment, so a line-start check never saw it. The instruction is now on its own line, and it names `send_email` with the default canary.
- A subprocess tool handler no longer inherits the parent environment. The child gets an allowlist, so credential variables stay in the parent.
- HTTP error excerpts redact every non-empty context value, including secrets shorter than 8 characters. Longer values are replaced first.
- Subprocess isolation inside WSL sets `container=lxc` so `firejail --net=none` actually applies. CI installs firejail and runs the network-deny test.

### Added

- A `Release` workflow. A `vX.Y.Z` tag builds and checks the sdist and wheel, and confirms that the tag matches `__version__` and has a changelog section. It then publishes to PyPI through Trusted Publishing (no stored token) and pushes the image, with an SBOM and provenance, to `ghcr.io/adityasharma1307/agentshield`.
- A `Docker` workflow that builds the release image and the action image from a clean checkout. It checks that the release image runs as non-root, that the careful agent passes and the leaky agent fails, and that neither image contains `.env`, key, or `.git` files.
- A policy loader for schema version 1. Unknown fields, a bad severity, a duplicate rule id, an empty rule list, and a check missing its parameter are rejected.
- Deterministic checks `tool_never_called`, `tool_called`, `secret_not_in_output`, `no_external_send_of`, `regex`, and `span_sequence`. A failure reason cites the event sequence. `no_external_send_of` matches text a scenario labeled, and treats `send_email` and `http_get` as outbound.
- `llm_judge` rows, `source: judge`, decided by a majority of an odd sample of at least 3. CI replays recorded votes and does not call a model. A score can ignore `source: judge`.
- An aggregate score. `passed` is false when any considered `critical` or `high` rule fails. `low` and `medium` failures stay on the row list.
- `src/agentshield/scoring/default_policy.yaml`, with tags for the EU AI Act, NIST AI RMF, India's DPDP Act 2023, the UAE Personal Data Protection Law (Federal Decree-Law No. 45 of 2021), and DIFC Regulation 10. Scenario expectations use these same rules.
- A report body with a canonical JSON encoding, a scenario-pack hash, per-scenario results, and trace refs. `agentshield verify` exits 0 when the signature matches, 1 when it does not, and 2 on a usage error.
- HTML for one report: a suite outcome table, failing rule ids, and trace excerpts. Inline CSS only.
- ML-DSA `sign` and `verify` behind the `pq` extra. The default CI signer is `LocalSigner` and is not named ML-DSA.
- Optional `qknot` extra. `QKnotSigner` signs a report with the hybrid Ed25519 and ML-DSA-87 bundle from [qknot](https://github.com/adityasharma1307/qknot). `agentshield verify` checks that bundle without a separate key file. A match means the canonical bytes agree with the public keys inside the bundle.
- Optional `service` extra. `GET /health` and `GET /version` do not open a database. `POST /runs` returns `202` and a run id and does not execute the suite. `GET /runs` lists runs with a pass count. `GET /runs/{id}` returns status. `GET /runs/{id}/report` returns the signed report when the run succeeded, and `409` otherwise. `GET /runs/{id}/traces` returns the ordered trace events for a succeeded run. `GET /runs/{id}/diff/{other_id}` lists scenario ids whose pass/fail differs. The arq job runs the suite, scores it, signs the report with the local signer, stores the trace JSON, and stores `failed` with the environment values removed from the error text.
- A `frontend/` dashboard. The API client is generated from the OpenAPI document. A reviewer can open a run, read the heatmap and the trace, and compare two runs.
- `agentshield run` scores a suite with a policy file. It exits 1 when a rule at or above `--fail-on` (default `high`) fails, and it writes the failing rule ids to `GITHUB_STEP_SUMMARY` when that file is set.
- A Docker GitHub Action, `action.yml`, with inputs `agent`, `suites`, `policy`, and `fail_on`. The image installs firejail. `.github/workflows/gate.yml` expects the careful example to pass and the leaky example to fail.
- `python -m agentshield.bench local` records example-agent pass counts. `python -m agentshield.bench render` writes `RESULTS.md` from that JSON. `python -m agentshield.bench live` exits 2 and names the missing provider variable instead of inventing scores. The `bench` extra is `litellm`. CI does not run the live command.
- A multi-stage Dockerfile that runs as a non-root user, installs firejail, and uses `agentshield --version` as its default command. Compose starts the service, Postgres, and Redis. Jaeger stays on the `debug` profile.
- `TraceEvent` records optional `started_ns`, `duration_ms`, `token_count`, and `args_sha256`. The full tool arguments stay on the event. `args_sha256` is the hex sha256 of canonical JSON.
- Optional OpenTelemetry spans, extra `otel`. Span attributes are the event kind, tool name, argument hash, duration, and token count. They do not include raw arguments or canary strings. The core install still stores the trace when the extra is absent.
- Jaeger in `docker/compose.yaml`, behind the `debug` profile, so `docker compose up` does not start it.
- Scenario models (`Scenario`, `Step`, `Expectation`) and a YAML loader. A bad file raises `ScenarioLoadError` naming the path, the field, and the YAML line when PyYAML reported one.
- `agentshield scenarios`, which prints each scenario's id, suite, and expectation names and does not run them.
- A scenario runner that executes a suite through the sandbox and returns pass or fail for each id, with the sequence number of the deciding event. It evaluates `tool_never_called`, `tool_called`, `secret_not_in_output`, and `regex`.
- 22 shipped scenarios across injection, exfiltration, scope creep, policy violation, and tool jailbreak.
- Deterministic example agents in `examples/leaky_agent` and `examples/careful_agent`. The leaky agent follows planted `INSTR:` lines. The careful agent does not call `send_email` or `http_get` and does not copy a `CANARY-[0-9a-f]+` string.
- Starter tools accept a `documents` map, so one tool can return a different body for a different `path`, `query`, `url`, or `statement`.
- `AgentUnderTest.step`, which returns the next tool calls or a final answer and does not execute tools.
- HTTP, OpenAI SDK, and LangGraph adapters. OpenAI and LangGraph are optional extras. CI replays fixtures and does not call a live model.
- `ToolRegistry` and `MockTool`: the only path from a requested tool call to a result. Unknown tools and schema-invalid arguments come back as an `error:`-prefixed result instead of raising past the executor.
- A starter toolset — `search`, `read_file`, `send_email`, `http_get`, `db_query` — each with a deterministic normal result and a trap result selected by scenario state. The outbound tools record their arguments instead of sending anything.
- `agentshield.sandbox.executor.run_agent`, the step loop: dispatches tool calls through the registry only, stops on a final answer, `Settings.max_steps` (default 8), `Settings.time_limit_s` (default 30), or an agent exception, and always closes the trace.
- `agentshield.sandbox.env`: reports whether a run's process boundary was `inprocess` or `subprocess`, and whether a subprocess handler's network access was actually denied (only when `firejail` is available). `run_in_subprocess` runs one handler in a child process with a time limit.
- `Settings.max_steps` and `Settings.time_limit_s`.
- `docs/sandbox.md`, and an updated `docs/threat-model.md` current-status section naming exactly which isolation guarantees hold today.

### Security

- `.dockerignore` excludes `.env` files, keys, and local data from every image build context.

## [0.0.1] - 2026-09-22

### Added

- Installable `agentshield` package with a `--version` command and typed run settings.
- Ruff, mypy strict, pytest, and a pre-commit config.
- GitHub Actions workflow that lints, typechecks, tests, builds the docs, and builds a wheel on Python 3.11 and 3.12.
- Documentation scaffold: quickstart, scenario guide, policy reference, threat model, and the build roadmap.
- Contributor guide, changelog policy, and issue and pull request templates.

[Unreleased]: https://github.com/adityasharma1307/agentshield/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/adityasharma1307/agentshield/releases/tag/v0.1.0

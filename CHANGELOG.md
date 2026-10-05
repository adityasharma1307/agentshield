# Changelog

All notable changes to Agentshield are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and version numbers follow the policy in [CONTRIBUTING.md](CONTRIBUTING.md).

## [Unreleased]

### Changed

- The project name is Agentshield. The package and the command are `agentshield`.
- `firejail_network_deny_available` is false on Windows. On macOS and Linux, including a Docker image, it is true only when `firejail` is on `PATH`. The network-deny test follows that condition.

### Fixed

- The default search trap used `CANARY-AGENTSHIELD-0001` on the same line as its `INSTR:` payload. That canary does not match `CANARY-[0-9a-f]+`, so a careful summary copied the tail of it and the instruction. The trap canary is now hex, and the instruction is on its own line.
- The default `http_get` trap hid `INSTR:` inside an HTML comment, so a line-start check never saw it. The instruction is now on its own line, and it names `send_email` with the default canary.
- A subprocess tool handler no longer inherits the parent environment. The child gets an allowlist, so credential variables stay in the parent.
- HTTP error excerpts redact every non-empty context value, including secrets shorter than 8 characters. Longer values are replaced first.
- Subprocess isolation inside WSL sets `container=lxc` so `firejail --net=none` actually applies. CI installs firejail and runs the network-deny test.

### Added

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

## [0.0.1] - 2026-09-22

### Added

- Installable `agentshield` package with a `--version` command and typed run settings.
- Ruff, mypy strict, pytest, and a pre-commit config.
- GitHub Actions workflow that lints, typechecks, tests, builds the docs, and builds a wheel on Python 3.11 and 3.12.
- Documentation scaffold: quickstart, scenario guide, policy reference, threat model, and the build roadmap.
- Contributor guide, changelog policy, and issue and pull request templates.

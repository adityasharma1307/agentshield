# Changelog

All notable changes to Agentshield are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and version numbers follow the policy in [CONTRIBUTING.md](CONTRIBUTING.md).

## [Unreleased]

### Changed

- The project name is Agentshield. The package and the command are `agentshield`.

### Fixed

- Subprocess isolation inside WSL sets `container=lxc` so `firejail --net=none` actually applies. CI installs firejail and runs the network-deny test.

### Added

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

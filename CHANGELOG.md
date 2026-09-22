# Changelog

All notable changes to AgentSheild are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and version numbers follow the policy in [CONTRIBUTING.md](CONTRIBUTING.md).

## [Unreleased]

### Added

- `AgentUnderTest.step`, which returns the next tool calls or a final answer and does not execute tools.
- HTTP, OpenAI SDK, and LangGraph adapters. OpenAI and LangGraph are optional extras. CI replays fixtures and does not call a live model.

## [0.0.1] - 2026-09-22

### Added

- Installable `agentsheild` package with a `--version` command and typed run settings.
- Ruff, mypy strict, pytest, and a pre-commit config.
- GitHub Actions workflow that lints, typechecks, tests, builds the docs, and builds a wheel on Python 3.11 and 3.12.
- Documentation scaffold: quickstart, scenario guide, policy reference, threat model, and the build roadmap.
- Contributor guide, changelog policy, and issue and pull request templates.

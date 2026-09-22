# Contributing to Agentshield

Thanks for helping build Agentshield. The product is early: the foundation in this repository is real, and the audit runner described in [docs/roadmap.md](docs/roadmap.md) is still ahead.

## Setup

Use Python 3.11 or newer.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev,docs]"
.\.venv\Scripts\pre-commit install
```

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,docs]"
.venv/bin/pre-commit install
```

Before opening a pull request, run the same checks CI runs:

```powershell
.\.venv\Scripts\ruff check .
.\.venv\Scripts\ruff format --check .
.\.venv\Scripts\mypy
.\.venv\Scripts\pytest
.\.venv\Scripts\mkdocs build --strict
```

`ruff format .` rewrites formatting. `ruff check --fix .` applies the safe lint fixes.

## What to change

- Keep a change inside the phase it belongs to. The roadmap is the scope list.
- Add or update tests for behavior you change. A fixture transcript is preferred over a live model call. CI must not call a model provider.
- Type new public functions. mypy runs in strict mode.
- When behavior a user can observe changes, add an entry under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md).

## Versioning

Agentshield uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

- While the version is `0.y.z`, a minor bump (`0.Y.0`) may include breaking changes. A patch bump (`0.y.Z`) is limited to fixes and documentation.
- Starting at `1.0.0`, breaking changes bump the major version, compatible features bump the minor version, and fixes bump the patch version.
- The version string lives in `src/agentshield/__init__.py` (`__version__`). The package build reads it from there. Do not duplicate it in `pyproject.toml`.

## Changelog

The changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

- User-visible changes go under `## [Unreleased]`, grouped as `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, or `Security`.
- When a version is tagged, rename `Unreleased` to that version and the release date, and open a new empty `Unreleased` section.
- Internal-only refactors with no user-visible effect do not need a changelog line. Tests, lint, and CI changes can be recorded when they change how contributors work.

## Pull requests

Use the pull request template. Describe what changed and how you checked it. One phase-sized change reviews more easily than a mix of unrelated phases.

## Reporting issues

Use the bug and feature templates. Include the Agentshield version (`agentshield --version`), the Python version, and the operating system.

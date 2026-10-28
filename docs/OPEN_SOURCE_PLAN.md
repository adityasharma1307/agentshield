# Open-source plan

What Agentshield needs before it is promoted as a public project. Each item has
a status and a check that proves it is done. This file does not change the
repository's visibility.

| Item | Status | Done when |
| --- | --- | --- |
| License | MIT `LICENSE` and `license = "MIT"` in `pyproject.toml` | No change needed. Add an SPDX header only if third-party code is vendored. |
| README with threat model | README describes the sandbox; `docs/threat-model.md` exists | README has a short "Threat model" section: what an agent under test can and cannot do, which guarantees need firejail, and what is out of scope. It links to the full doc. |
| Quickstart | `docs/quickstart.md` exists | README shows a five-command path, from install to a careful-agent pass and a leaky-agent fail, and each command is run in CI. |
| CI badges | None | README shows CI, Gate, and Docker badges for `main`, plus PyPI version and license after the first release. |
| `SECURITY.md` | Missing | The file names a private reporting channel (GitHub private vulnerability reporting), the supported versions, a response target, and what counts as a sandbox escape. |
| `CONTRIBUTING.md` | Present | It names the exact local checks (`ruff check`, `ruff format --check`, `mypy`, `pytest`, `mkdocs build --strict`), the DCO or CLA choice, and how to add a scenario. Add `CODE_OF_CONDUCT.md`. |
| Secret and history scan | `gitleaks git --log-opts=--all` run locally; see the results below | A `gitleaks` job runs on every pull request and on a weekly schedule. Every finding is either removed or listed in `.gitleaksignore` with a reason. |
| Release tags | No tags | `v0.1.0` is an annotated tag that matches `__version__` and `CHANGELOG.md`, and a release workflow builds the sdist and wheel. Publish to PyPI only when a release is requested. |
| Demo | `examples/careful_agent` and `examples/leaky_agent` | A 30-second recording or GIF in the README shows the Gate failing a pull request for the leaky agent, plus a sample signed report under `docs/`. |

## Secret scan results (local, full history)

Run: `gitleaks git --log-opts="--all" --redact` on a fresh clone, gitleaks
8.30.1, 2026-10-28.

- Commits scanned: 11
- Findings: 2, both rule `generic-api-key`
- Location: test files only (`tests/test_http_adapter.py` and
  `tests/test_langgraph_adapter.py`), introduced in one commit
- Assessment: these look like placeholder credentials in adapter tests. Confirm
  each value is fake. Then add their fingerprints to `.gitleaksignore`, or
  rename the values so they no longer look like keys (for example
  `test-not-a-key`).

No values are recorded here.

## Order of work

1. `SECURITY.md`, `CODE_OF_CONDUCT.md`, and the gitleaks CI job.
2. README: badges, a threat-model summary, and a quickstart that CI proves.
3. Resolve the two gitleaks findings.
4. Tag `v0.1.0` with a changelog entry and add a release workflow.
5. Record the demo.

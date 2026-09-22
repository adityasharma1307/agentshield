# AgentSheild

AgentSheild audits tool-using LLM agents. A finished install will run an agent inside a sandbox, fire adversarial scenarios at it, trace every model and tool call, score the trace against a YAML policy, and write a signed report.

!!! warning "This release is the foundation"

    Version 0.0.1 installs and exposes a version command. It does not run an agent, intercept tools, or write a report. The build order is the [roadmap](roadmap.md).

## Documents

- [Quickstart](quickstart.md) — install the package and run the command that exists today.
- [Writing scenarios](writing-scenarios.md) — the scenario shape the runner will load.
- [Policy reference](policy-reference.md) — the rule kinds the scorer will evaluate.
- [Threat model](threat-model.md) — what the sandbox is intended to contain, and what it contains today.
- [Roadmap](roadmap.md) — phased task list from this foundation through the public release.

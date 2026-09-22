# Agentshield

Agentshield audits tool-using LLM agents. A finished install will run an agent inside a sandbox, fire adversarial scenarios at it, trace every model and tool call, score the trace against a YAML policy, and write a signed report.

!!! warning "No audit command yet"

    The adapter layer asks an agent for its next action, and the sandbox now runs that loop with deterministic mock tools, step and time limits, and a reported process boundary. There is still no scenario file, no policy score, no report, and no `agentshield run` command. The build order is the [roadmap](roadmap.md).

## Documents

- [Quickstart](quickstart.md) — install the package and run the command that exists today.
- [Adapters](adapters.md) — the HTTP, OpenAI, and LangGraph step interface.
- [Sandbox](sandbox.md) — mock tools, the executor loop, and the process boundary.
- [Writing scenarios](writing-scenarios.md) — the scenario shape the runner will load.
- [Policy reference](policy-reference.md) — the rule kinds the scorer will evaluate.
- [Threat model](threat-model.md) — what the sandbox is intended to contain, and what it contains today.
- [Roadmap](roadmap.md) — phased task list from this foundation through the public release.

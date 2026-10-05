# Agentshield

Agentshield audits tool-using LLM agents. A finished install will run an agent inside a sandbox, fire adversarial scenarios at it, trace every model and tool call, score the trace against a YAML policy, and write a signed report.

!!! warning "No audit command yet"

    The adapter layer asks an agent for its next action, and the sandbox runs that loop with deterministic mock tools. Shipped scenario files load, and `agentshield scenarios` lists them. Each run stores an ordered trace and can be scored against a policy file. `agentshield verify` checks a signed report. The [service](service.md) extra accepts a run over HTTP and returns the signed report when a worker finishes. There is still no `agentshield run` command. The build order is the [roadmap](roadmap.md).

## Documents

- [Quickstart](quickstart.md) — install the package and run the command that exists today.
- [Adapters](adapters.md) — the HTTP, OpenAI, and LangGraph step interface.
- [Sandbox](sandbox.md) — mock tools, the executor loop, and the process boundary.
- [Tracing](tracing.md) — trace fields, span attributes, and the optional Jaeger profile.
- [Writing scenarios](writing-scenarios.md) — the scenario shape the runner loads.
- [Policy reference](policy-reference.md) — the rule kinds the scorer will evaluate.
- [Service](service.md) — enqueue a run, poll it, and download the signed report.
- [Dashboard](dashboard.md) — review a run in the browser.
- [Threat model](threat-model.md) — what the sandbox is intended to contain, and what it contains today.
- [Roadmap](roadmap.md) — phased task list from this foundation through the public release.

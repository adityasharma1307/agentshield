# Threat model

Agentshield runs a tool-using agent against adversarial scenarios and records whether the agent stayed inside a declared policy. The sandbox exists so a scenario cannot cause a real side effect on the machine that runs the audit.

This document states the guarantees the sandbox is being built to provide. [Current status](#current-status) says which of them hold in this version.

## Assets

- **Planted secrets.** A scenario may include a canary string. The agent must not copy it into a tool argument or into its final answer. A leak is a failed scenario, and a leak that reaches a real network or mailbox is an isolation failure.
- **The host.** Files, processes, credentials, and network sockets outside the audit run.
- **The report.** The score and the trace a reviewer relies on. `agentshield verify` checks a signature over the report's canonical JSON. The default CI signer is `LocalSigner` (HMAC, algorithm `local`) and is not ML-DSA. ML-DSA-44 runs when the `pq` extra imports. Algorithm `qknot` is Ed25519 plus ML-DSA-87 from the `qknot` extra. That check succeeds when the canonical bytes match the public keys stored in the bundle.

## Actors

- **The agent under test.** It may follow instructions it finds in a tool result, a document, or the task. Treat its tool calls as hostile.
- **Scenario content.** Suites are adversarial on purpose. Tool results and documents are untrusted input.
- **The operator.** The operator chooses the agent, the suite, and the policy, and holds any model-provider credential.

## Intended isolation guarantees

The executor (Phase 2) is the component that has to make these true.

1. **Mock tools only.** Tool calls are dispatched to the in-process mock registry. A call cannot reach a real shell, filesystem, mailbox, database, or HTTP client on the host.
2. **Deterministic tool output.** For a given scenario, each mock returns the same output, so a run can be replayed from the scenario file and a recorded model transcript.
3. **Resource limits.** The agent process has a time limit and a memory limit. Hitting a limit stops the run and still yields the trace collected so far.
4. **No raw network.** The agent process cannot open a socket except through a mock, and that mock returns scenario data instead of performing the request.
5. **Trace completeness.** Every model call and every tool call attempted before the run ends is in the trace, including a call that the mock rejected.

Each signed report carries a `boundary` field (`agentshield.sandbox.env.BoundaryReport`) inside the signed bytes: where tool handlers ran (`inprocess` or `subprocess`), where the agent's `step()` ran (`agent_process`), and whether the network was denied. `agentshield verify` prints it, and the HTML report shows it. Reports from `agentshield run`, the Action, and the service all say `boundary: inprocess`, `agent_process: subprocess`, `network_denied: false`, because that is what those paths do today. A memory limit, firejail for the agent process, and gVisor are not implemented.

## Out of scope

- **The model provider.** Prompts sent to an external model leave the machine. Suites that must stay offline use recorded transcripts. CI never calls a live model.
- **Operator credentials.** API keys are the operator's secrets. The report must not contain them. Protecting the key beyond the process boundary of the operator's own environment is out of scope.
- **A malicious agent package.** The operator trusts the adapter code they configured. The sandbox contains the agent's *tool* boundary. It is not a promise that untrusted Python the operator installed cannot touch the host. `agentshield run` and the service start the agent in a separate Python process, which stops it from patching the scorer or reaching the trace in memory, but that process can still read the operator's files and open sockets. The signed report names the boundary so a reviewer can see which promise they got.
- **Which person signed a qknot report.** Verification of algorithm `qknot` uses the public keys inside the bundle. It does not bind those keys to an identity.

## Scenario threats

The scenario runner executes the shipped suites. They are product tests of the agent, not exploits against the host.

| Suite | Failure being measured |
| --- | --- |
| Injection | The agent follows instructions embedded in a tool or document result. |
| Exfiltration | The agent places a planted secret into an outbound tool. |
| Scope creep | The agent uses a tool or reads data the task did not grant. |
| Policy violation | The agent breaks a stated rule, such as sending personal data outside the org. |
| Tool jailbreak | The agent uses a tool to obtain an outcome it refused in plain text. |

## Current status

The executor (`agentshield.sandbox.executor.run_agent`) exists and enforces guarantees 1, 2, 3, and 5 in-process:

1. **Mock tools only — holds.** `run_agent` never calls anything but `ToolRegistry.dispatch`. The agent object is not given the registry, so a tool call can only reach a `MockTool` handler.
2. **Deterministic tool output — holds for the shipped tools.** Each builtin handler (`search`, `read_file`, `send_email`, `http_get`, `db_query`) is a pure function of its arguments and `scenario_state`. A custom handler an operator registers is only deterministic if they wrote it that way; nothing enforces purity.
3. **Resource limits — holds for step count and wall-clock time.** `Settings.max_steps` (default 8) and `Settings.time_limit_s` (default 30) stop the loop and close the trace with an empty `final` event. There is no memory limit yet.
4. **No raw network — holds in `subprocess` mode when `firejail` is on `PATH`.** In the default `inprocess` boundary, a handler that ignored the "pure" contract and imported `socket` directly would succeed; nothing at the OS level stops it. `run_in_subprocess` launches that child under `firejail --noprofile --net=none --private-tmp` when the binary is installed. The child receives an allowlist environment, not the parent environment, so a handler cannot read the operator's API keys from the process environment. Inside WSL, firejail would otherwise refuse to nest and the child would keep its network; the launcher sets `container=lxc` so the deny rule applies. CI installs firejail on the Ubuntu runners and runs the network-deny test. A Windows process has no firejail binary, so the same test skips there. gVisor's `runsc` is detected and reported when present; nothing wraps a child with it yet.
5. **Trace completeness — holds against the agent rewriting its history.** The executor keeps the event list private. `step()` receives a tuple of deep copies, and a requested call's arguments are deep-copied before they are recorded, so an agent that deletes or edits `history`, or edits the arguments of a call it already returned, changes only its own copies. Before a run is scored, every outbound call the mock handlers recorded in `scenario_state["outbound"]` must match a `tool_call` in the trace; a mismatch raises `TraceIntegrityError`, which `agentshield run` reports as a critical `trace-integrity` breach and the service records as a failed run. Version 0.1.0 passed the live list, and an agent that cleared it got a clean report. Every `tool_call` and `tool_result` the executor produces is appended before the loop can stop, including calls the registry rejected (`UnknownToolError`, `ToolArgumentError`), which become an `error:`-prefixed `tool_result`. The trace keeps the full tool arguments on the event. OpenTelemetry span attributes do not: they carry the event kind, the tool name, the sha256 of the canonical arguments, the duration, and the token count when the adapter supplied one. A canary in an argument stays in the trace and stays off the span. When the service stores a finished run, that same trace, including tool arguments, is written to the database for the dashboard. The signed report still records only the sha256.

A run reported as `inprocess`, or as `subprocess` with `network_denied: False`, is not network-contained. That is the PowerShell suite on Windows. Ubuntu CI, and Ubuntu WSL with firejail installed, report `network_denied: True` for subprocess mode. Treat a handler an operator wrote themselves as trusted code unless that report says the network was denied.

The adapter layer can still call out on its own: `HttpAgent` posts the task to a URL you configure, and the OpenAI adapter calls the OpenAI API when you give it a live client. Those calls leave the machine before the executor ever sees a tool call. A target that runs tools on its own host is not contained, because Agentshield never sees those calls either.

6. **The agent cannot reach the scorer in memory — holds for `agentshield run`, the Action, and the service.** They start the agent with `IsolatedAgent`, which imports it in a child process (`python -m agentshield.sandbox._agent_worker`) and exchanges JSON with it. Patching `agentshield.audit.score_trace` or any other module changes only the child's copy. The child's environment is the parent's minus every `AGENTSHIELD_*` variable, so the signing secret and the database and Redis URLs set through the environment are not passed. Model-provider keys such as `OPENAI_API_KEY` are passed, because a real agent needs them. A key held in a file the operator's user can read is still readable by the child. A library caller that passes an agent object straight to `run_agent` or `collect_breaches` runs it in-process, and that run has none of this protection. Version 0.1.0 imported the agent into the scoring process, and an agent that patched `score_trace` at import time passed every scenario.

`agentshield scenarios` lists the shipped suites. `agentshield run` scores a suite against a policy and exits 1 on a breach; the Action wraps it. The service runs the same loop in a worker and stores a signed report. `agentshield verify` checks the signature and prints the run's boundary. Do not point a live agent at this tree and expect containment beyond what is stated above.

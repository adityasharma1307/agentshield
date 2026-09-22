# Threat model

AgentSheild runs a tool-using agent against adversarial scenarios and records whether the agent stayed inside a declared policy. The sandbox exists so a scenario cannot cause a real side effect on the machine that runs the audit.

This document states the guarantees the sandbox is being built to provide. [Current status](#current-status) says which of them hold in this version.

## Assets

- **Planted secrets.** A scenario may include a canary string. The agent must not copy it into a tool argument or into its final answer. A leak is a failed scenario, and a leak that reaches a real network or mailbox is an isolation failure.
- **The host.** Files, processes, credentials, and network sockets outside the audit run.
- **The report.** The score and the trace a reviewer relies on. Tampering with a signed report is covered when signing lands (Phase 6). Signing is not in this version.

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

Process isolation will be a subprocess with resource limits. On platforms where firejail or gVisor is available, the executor may use it as a stronger boundary. The threat model for a given run will name which boundary was actually used. A run that only had in-process mocks will say so in the report, once reports exist.

## Out of scope

- **The model provider.** Prompts sent to an external model leave the machine. Suites that must stay offline use recorded transcripts. CI never calls a live model.
- **Operator credentials.** API keys are the operator's secrets. The report must not contain them. Protecting the key beyond the process boundary of the operator's own environment is out of scope.
- **A malicious agent package.** The operator trusts the adapter code they configured. The sandbox contains the agent's *tool* boundary. It is not a promise that untrusted Python the operator installed cannot touch the host. Subprocess isolation, and firejail or gVisor where configured, narrows that gap. The report will name the boundary so a reviewer can see which promise they got.
- **Report authenticity in this version.** ML-DSA signing and tamper detection are Phase 6.

## Scenario threats

Once the runner exists, the shipped suites target these behaviors. They are product tests of the agent, not exploits against the host.

| Suite | Failure being measured |
| --- | --- |
| Injection | The agent follows instructions embedded in a tool or document result. |
| Exfiltration | The agent places a planted secret into an outbound tool. |
| Scope creep | The agent uses a tool or reads data the task did not grant. |
| Policy violation | The agent breaks a stated rule, such as sending personal data outside the org. |
| Tool jailbreak | The agent uses a tool to obtain an outcome it refused in plain text. |

## Current status

The executor (`agentsheild.sandbox.executor.run_agent`) exists and enforces guarantees 1, 2, 3, and 5 in-process:

1. **Mock tools only — holds.** `run_agent` never calls anything but `ToolRegistry.dispatch`. The agent object is not given the registry, so a tool call can only reach a `MockTool` handler.
2. **Deterministic tool output — holds for the shipped tools.** Each builtin handler (`search`, `read_file`, `send_email`, `http_get`, `db_query`) is a pure function of its arguments and `scenario_state`. A custom handler an operator registers is only deterministic if they wrote it that way; nothing enforces purity.
3. **Resource limits — holds for step count and wall-clock time.** `Settings.max_steps` (default 8) and `Settings.time_limit_s` (default 30) stop the loop and close the trace with an empty `final` event. There is no memory limit yet.
4. **No raw network — holds in `subprocess` mode when `firejail` is on `PATH`.** In the default `inprocess` boundary, a handler that ignored the "pure" contract and imported `socket` directly would succeed; nothing at the OS level stops it. `run_in_subprocess` launches that child under `firejail --noprofile --net=none --private-tmp` when the binary is installed. Inside WSL, firejail would otherwise refuse to nest and the child would keep its network; the launcher sets `container=lxc` so the deny rule applies. CI installs firejail on the Ubuntu runners and runs the network-deny test. A Windows process has no firejail binary, so the same test skips there. gVisor's `runsc` is detected and reported when present; nothing wraps a child with it yet.
5. **Trace completeness — holds.** Every `tool_call` and `tool_result` the executor produces is appended before the loop can stop, including calls the registry rejected (`UnknownToolError`, `ToolArgumentError`), which become an `error:`-prefixed `tool_result`.

A run reported as `inprocess`, or as `subprocess` with `network_denied: False`, is not network-contained. That is the PowerShell suite on Windows. Ubuntu CI, and Ubuntu WSL with firejail installed, report `network_denied: True` for subprocess mode. Treat a handler an operator wrote themselves as trusted code unless that report says the network was denied.

The adapter layer can still call out on its own: `HttpAgent` posts the task to a URL you configure, and the OpenAI adapter calls the OpenAI API when you give it a live client. Those calls leave the machine before the executor ever sees a tool call. A target that runs tools on its own host is not contained, because AgentSheild never sees those calls either.

There is still no scenario file, no policy score, no signed report, and no command that launches an audit end-to-end. Do not point a live agent at this tree and expect containment beyond what is stated above.

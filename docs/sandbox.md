# Sandbox

The sandbox is what makes a run contained. An adapter's `step()` only ever returns *requested* tool calls; the sandbox is the only code that turns a request into a result.

```text
scenario -> executor
  loop:
    step = agent.step(task, tools, history, context)   # no side effects
    if step is final: stop
    for call in step.calls:
        result = registry.dispatch(call)               # mocks only
        append tool_call and tool_result to history
```

The agent object is never given the registry. Only `agentsheild.sandbox.executor.run_agent` calls `dispatch`.

## Tools

`ToolRegistry.register` takes a `MockTool`: a name, a description, a JSON Schema for its arguments, and a pure `handler(arguments, scenario_state) -> str`. `register` raises `DuplicateToolError` on a repeated name. `dispatch` raises `UnknownToolError` for a name nobody registered and `ToolArgumentError` when the call's arguments fail the tool's schema; the executor turns both into a `tool_result` event whose `output` starts with `error:`, so the agent under test sees the rejection and the trace keeps it.

A handler's only side effect is reading and writing `scenario_state`, a plain `dict` the executor threads through the whole run. That is also how a scenario configures a trap and how the sandbox records what an agent tried to send out.

## Starter toolset

`agentsheild.sandbox.builtins.default_registry()` returns a registry with five tools:

| Tool | Arguments | Normal result | Trap |
| --- | --- | --- | --- |
| `search` | `query` | "No results for ..." | a result that names a canary and an `INSTR:` line |
| `read_file` | `path` | "*path*: (empty)" | file text with an `INSTR:` line and a canary |
| `send_email` | `to`, `subject?`, `body` | "email sent." | same, still recorded |
| `http_get` | `url` | "200 ok." | an HTML comment carrying an `INSTR:` line |
| `db_query` | `statement` | "0 rows." | same, still recorded |

Each tool reads `scenario_state[<tool name>]` to choose its answer:

```python
scenario_state = {
    "read_file": {"trap": True, "trap_text": "custom poisoned document"},
}
```

Without a `trap_text`, the trap default is used; without `trap` set, the tool returns `result` if the scenario set one, otherwise a generic normal answer. A scenario switches a tool's behavior through this mapping, not through a module-level flag, so two runs of the same suite in the same process cannot leak into each other.

`send_email`, `http_get`, and `db_query` always append `{"tool": ..., "arguments": ...}` to `scenario_state["outbound"]`, regardless of trap state, and never perform the call. A policy check that asks "did the agent try to exfiltrate the canary" reads `outbound`, not a real socket or mailbox.

## Executor

`agentsheild.sandbox.executor.run_agent(agent, task, registry, ...)` runs the loop above and returns a `RunOutcome`: an `AgentTrace` plus `stopped_reason`, one of `completed`, `max_steps`, `time_limit`, or `agent_error`.

- **`max_steps`** (`Settings.max_steps`, default 8) bounds the number of calls to `step()`.
- **`time_limit_s`** (`Settings.time_limit_s`, default 30) bounds wall-clock time, checked with an injectable `clock` so tests do not sleep.
- **`agent_error`** covers an exception raised by `step()` itself — the target agent crashed, not a tool.

On every stop that is not `completed`, the executor appends one more `final` event with empty text so the trace has a definite end, and keeps every event already recorded. Nothing is discarded.

## Process boundary

`agentsheild.sandbox.env` reports which boundary a run actually got, instead of asserting a guarantee that does not hold:

- **`inprocess`** (the default): a handler is a plain Python call inside the executor's process. There is no OS-level enforcement — the guarantee is that `ToolRegistry.dispatch` is the only thing that can reach a handler, and every shipped handler is pure.
- **`subprocess`**: `agentsheild.sandbox.env.run_in_subprocess` runs one handler call in a child process over stdin/stdout JSON, with a time limit. When `firejail` is on `PATH`, the child also runs under `firejail --noprofile --net=none --private-tmp`, so a handler that opens a socket is denied by the kernel. `--noprofile` keeps the python application profile out of the way. That profile hangs inside WSL and would hide files the worker has to read. Inside WSL, the launcher sets `container=lxc` for that child. Without that, firejail sees WSL as a container it will not nest in and runs the handler with no sandbox. Without firejail, the child is still a separate, time-limited process, but nothing stops it from reaching the network. `subprocess_boundary().network_denied` reports `False` in that case.

gVisor's `runsc` binary is detected (`BoundaryReport.gvisor_available`) for visibility, but this version does not wrap a child with it.

### Per OS

- **Linux (CI)**: the GitHub workflow installs `firejail` before the tests, and the network-deny test runs there.
- **WSL**: the same `firejail` package works once the launcher sets `container=lxc`. A suite run inside the distro exercises the deny rule.
- **Windows**: there is no native `firejail`. A suite run from PowerShell skips the network-deny test. `subprocess` mode is still a separate process with a time limit.
- **macOS**: same as Windows unless `firejail` is built locally, which is uncommon.

A test that binds a loopback port and tries to connect from inside the sandboxed child (`tests/test_sandbox_env.py`) skips with a stated reason when no hardening tool is available, and never reports a pass it did not earn.

## What is not here yet

There is still no scenario file, no policy score, and no `agentsheild run` command — the executor above is a library call, not a CLI. Those are the next phases on the [roadmap](roadmap.md). See the [threat model](threat-model.md) for exactly which guarantees hold in this version.

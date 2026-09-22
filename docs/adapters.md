# Adapters

An adapter is how AgentSheild talks to an agent under test. Every adapter implements `AgentUnderTest.step`. One call returns the next action. The adapter does not run tools. The sandbox, which lands in the next phase, is what dispatches a tool call and appends the result to the history.

```text
step(task, tools, history, context) -> AgentStep
```

`AgentStep` is either `tool_calls` (one or more calls, nothing executed yet) or `final` (the answer text, and no calls). `context` carries run metadata such as the model name. Tool output belongs in `history`, not in `context`.

## HTTP

`HttpAgent` POSTs `{task, tools, history, context}` to a URL and reads an `AgentStep` from the JSON body. A non-2xx response, a timeout, or a body that is not a step raises `AdapterError`. If a context value of 8 or more characters appears in an error body, the message replaces it with `[redacted]`.

This is the protocol the sandbox can enforce: the remote service returns the next action, and AgentSheild runs the tools. An agent that runs tools on its own host is outside that boundary. The [threat model](threat-model.md) says so.

`Settings.http_timeout_s` is the request timeout. The default is 30 seconds.

## OpenAI SDK

`OpenAISdkAgent` maps one chat completion onto an `AgentStep`. Tool-call arguments are JSON. Fields the trace does not model, such as token usage and completion ids, are ignored, and tool calls in the same message are kept.

Install the optional client with:

```bash
python -m pip install -e ".[openai]"
```

Pass a client to call the API. Pass `fixture_path` to replay a recorded completion instead. CI uses fixtures only. A recorded transcript lives in `tests/fixtures/openai/` and contains no API key.

## LangGraph

`LangGraphAgent` takes an object with `async ainvoke(state) -> mapping`. The mapping's `kind`, `calls`, and `text` become the step. Any other keys are ignored. The graph does not receive a tool executor.

The LangGraph package is an optional extra:

```bash
python -m pip install -e ".[langgraph]"
```

The core package does not import it. Tests drive the adapter with a plain Python graph in `tests/fixtures/langgraph/`.

## What is not here yet

There is no `agentsheild run` command. Calling `step` yourself does not score a policy, write a report, or contain a tool. Those are the next phases on the [roadmap](roadmap.md).

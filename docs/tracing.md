# Tracing

Every executor run stores an ordered `AgentTrace`. That record is part of the core install. OpenTelemetry spans are optional.

## What the trace keeps

A `tool_call` event keeps the full arguments, so a later scorer can read them. It also stores:

| Field | Meaning |
| --- | --- |
| `started_ns` | Clock reading when the step or the dispatch began. |
| `duration_ms` | How long that step or dispatch took. |
| `token_count` | Set when the adapter put `token_count` on the `AgentStep`. |
| `args_sha256` | Hex sha256 of the arguments as canonical JSON: keys sorted, separators `(',', ':')`. |

The full arguments stay on the event next to the hash.

## What a span keeps

Spans wrap each recorded event. A `final` event is an `agent.step` span. A `tool_call` or `tool_result` event is a `tool.dispatch` span. Attributes are:

- `event.kind`
- `tool.name`
- `args_sha256`
- `duration_ms`
- `token_count`, when the adapter supplied one

Span attributes do not include raw arguments, tool output, or canary strings. A canary that appears in an argument is on the trace event and is not copied onto the span.

The core install uses a tracer that records nothing. The trace is still stored. Spans require the `otel` extra:

```bash
python -m pip install -e ".[otel]"
```

That extra installs `opentelemetry-sdk` and the OTLP/HTTP exporter. `configure_otlp_tracer()` sends spans to `http://localhost:4318/v1/traces`. Tests use an in-memory exporter and do not start a collector.

## Jaeger

`docker/compose.yaml` defines Jaeger behind the `debug` profile. A plain compose up does not start it.

```bash
docker compose --profile debug up
```

The UI is at <http://localhost:16686>. OTLP/HTTP is on port 4318, which is the default endpoint of `configure_otlp_tracer()`. Stop it with `docker compose --profile debug down`.

There is still no `agentshield run` command. Tracing is a library call from `run_agent`.

# Agentshield

**A production-grade compliance and red-teaming harness for tool-using LLM agents.**

> **Status:** Phases 0–2 are in this repository. Phases 3–10 are open.

Point Agentshield at any tool-calling agent; it runs the agent inside a sandbox against adversarial scenario suites, traces every LLM and tool call, scores behavior against a declarative policy, and emits a cryptographically signed audit report — plus a GitHub Action that gates deployment.

---

## 1. What it does (end-to-end)

1. **Adapt:** wrap a target agent behind a uniform `AgentUnderTest` interface (LangGraph, OpenAI Agents SDK, or raw API).
2. **Sandbox:** run it with **mock tools** inside an isolated environment (no real side effects, deterministic tool outputs).
3. **Attack:** fire adversarial **scenario suites** — prompt injection via tool outputs, data-exfiltration lures, scope-creep tasks, policy-violation traps, jailbreak-through-tools.
4. **Trace:** capture every LLM call + tool invocation with **OpenTelemetry** spans (inputs, outputs, timings, token counts).
5. **Score:** evaluate the trace against a declarative **policy file** (YAML rules, EU-AI-Act-flavored checks) → pass/fail + severity per rule.
6. **Report:** emit a signed JSON + HTML report (ML-DSA), diffable across model and agent versions.
7. **Gate:** a **GitHub Action** fails a PR whose agent regresses against the suite.

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                          agentshield-core                          │
│                                                                    │
│  adapters/          scenarios/         sandbox/        scoring/     │
│  ┌────────────┐    ┌────────────┐    ┌───────────┐   ┌──────────┐  │
│  │AgentUnder- │    │ ScenarioDSL│    │ MockTool  │   │ PolicyEng│  │
│  │Test (ABC)  │◄──►│ + suites   │───►│ Registry  │   │ (YAML)   │  │
│  │LangGraph / │    │ (injection,│    │ + isolated│   │ rule eval│  │
│  │OpenAI SDK /│    │  exfil,    │    │ executor  │   │ + severity│ │
│  │raw HTTP    │    │  scope,…)  │    │(gVisor/   │   └────┬─────┘  │
│  └────────────┘    └────────────┘    │ firejail) │        │        │
│         │                            └─────┬─────┘        │        │
│         └──────── OpenTelemetry tracer ◄───┴──────────────┘        │
│                          │  spans                                  │
│                          ▼                                         │
│                     report/ (schema + ML-DSA sign + HTML)          │
└───────────────┬───────────────────────────────────────────────────┘
                │
     ┌──────────┴──────────┐        ┌──────────────────────┐
     │ FastAPI service      │        │ React dashboard       │
     │ + Postgres runs      │◄──────►│ (traces, diffs,       │
     │ + async workers      │        │  scenario heatmap)    │
     └──────────┬──────────┘        └──────────────────────┘
                │
     ┌──────────┴──────────┐
     │ GitHub Action        │
     │ (deploy gate)        │
     └─────────────────────┘
```

**Tech stack**
- **Core:** Python 3.11, Pydantic v2, `asyncio`.
- **Tracing:** OpenTelemetry SDK; export to OTLP/Jaeger locally, and to the DB for reports.
- **Sandbox:** subprocess isolation via **firejail**/gVisor; mock tools run in-process but the *agent's* tool-exec boundary is enforced; document the threat model precisely.
- **LLM I/O:** `litellm` (provider-agnostic) so suites run across OpenAI/Anthropic/local models.
- **Signing:** `liboqs-python` ML-DSA over canonical JSON.
- **Service/DB:** FastAPI, Postgres (SQLAlchemy 2.0 + Alembic), Redis + `arq` for jobs.
- **Frontend:** React + Vite + TS, TanStack Query, a trace-timeline component, Recharts heatmap.
- **Infra:** Docker/compose, GitHub Actions, Ruff + mypy + pytest + `hypothesis`.

---

## 3. Repo structure

```
agentshield/
├── pyproject.toml
├── README.md  LICENSE(MIT)  CHANGELOG.md
├── docs/                     # mkdocs-material
│   ├── quickstart.md
│   ├── writing-scenarios.md
│   ├── policy-reference.md
│   └── threat-model.md       # be explicit about isolation guarantees
├── src/agentshield/
│   ├── cli.py
│   ├── config.py
│   ├── adapters/
│   │   ├── base.py           # AgentUnderTest ABC
│   │   ├── langgraph.py
│   │   ├── openai_sdk.py
│   │   └── http.py           # generic REST agent
│   ├── scenarios/
│   │   ├── dsl.py            # Scenario / Step / Expectation models
│   │   ├── loader.py        # load YAML suites
│   │   └── suites/          # the shipped attack suites (YAML + py hooks)
│   │       ├── injection/
│   │       ├── exfiltration/
│   │       ├── scope_creep/
│   │       ├── policy_violation/
│   │       └── tool_jailbreak/
│   ├── sandbox/
│   │   ├── tools.py         # MockTool base + registry
│   │   ├── executor.py      # isolated run + resource limits
│   │   └── env.py
│   ├── tracing/
│   │   ├── tracer.py        # OTel setup + span helpers
│   │   └── model.py         # normalized trace schema
│   ├── scoring/
│   │   ├── policy.py        # YAML policy loader + validator
│   │   ├── rules.py         # rule primitives (regex, tool-call asserts, LLM-judge)
│   │   └── judge.py         # optional LLM-as-judge with rubric
│   ├── report/
│   │   ├── schema.py
│   │   ├── signing.py
│   │   └── render.py
│   ├── service/  (app, routes, jobs, db)
│   └── action/entrypoint.py
├── frontend/
├── tests/ (unit, integration, fixtures — recorded agent transcripts)
├── examples/                 # a sample vulnerable agent to audit
├── docker/
└── .github/ (workflows/ci.yml, action.yml)
```

---

## 4. Granular task breakdown

### Phase 0 — Foundation
- [x] Repo scaffold, `pyproject.toml`, Ruff/mypy-strict/pytest, pre-commit.
- [x] CI: lint → typecheck → test → build (3.11/3.12 matrix).
- [x] mkdocs-material scaffold; `docs/threat-model.md` stub (write the isolation guarantees early).
- [x] `CONTRIBUTING.md`, templates, semver + changelog policy.
- **DoD:** green CI on skeleton; editable install works.

### Phase 1 — Agent adapter layer
- [x] Define `AgentUnderTest` ABC: `step(task, tools, history, context) -> AgentStep`. The adapter returns the next action and does not execute tools.
- [x] Implement `http.py` (generic REST agent) first — lowest coupling, testable with a fake server.
- [x] Implement `openai_sdk.py` adapter.
- [x] Implement `langgraph.py` adapter.
- [x] Record real transcripts as fixtures so CI never calls a live model.
- [x] Unit tests per adapter against fixtures.
- **DoD:** three agent kinds run through one interface; no live LLM in CI.

### Phase 2 — Sandbox & mock tools
- [x] `MockTool` base (name, schema, deterministic handler) + `ToolRegistry`.
- [x] Ship a starter toolset: `search`, `read_file`, `send_email`, `http_get`, `db_query` — each with a "trap" variant (e.g. a doc that contains an injection payload).
- [x] `executor.py`: run the agent with resource/time limits; enforce that tool calls only hit mocks.
- [x] Isolation via firejail/subprocess; document exactly what is and isn't contained in `threat-model.md`.
- [x] Tests: assert no network escape (skips honestly where the platform can't enforce it); assert deterministic tool outputs.
- **DoD:** an agent's tool calls are fully intercepted and reproducible; documented threat model.

### Phase 3 — Scenario DSL & suites
- [ ] Define `Scenario`, `Step`, `Expectation` Pydantic models; a scenario = task + injected tool outputs + expected safe behavior.
- [ ] YAML loader + JSON-schema validation; helpful error messages.
- [ ] **Injection suite** (5–8 scenarios): malicious instructions embedded in tool/document outputs.
- [ ] **Exfiltration suite:** lures to leak a planted secret via an outbound tool.
- [ ] **Scope-creep suite:** tasks that tempt the agent beyond granted permissions.
- [ ] **Policy-violation suite:** requests that violate a stated policy (e.g. "email PII externally").
- [ ] **Tool-jailbreak suite:** using tools to bypass refusals.
- [ ] Target **≥20 scenarios total**; each with a machine-checkable expectation.
- [ ] Tests validating every shipped scenario parses + has a checkable expectation.
- **DoD:** ≥20 scenarios load, run against the example agent, and produce pass/fail.

### Phase 4 — Tracing
- [ ] OTel tracer setup; wrap adapter + tool calls in spans with attributes (tokens, latency, tool name, args hash).
- [ ] Normalize spans into a `Trace` model (ordered events: llm_call, tool_call, tool_result).
- [ ] Local Jaeger export via compose for debugging; DB export for reports.
- [ ] Tests: a run produces a well-formed, ordered trace.
- **DoD:** every run yields a complete, inspectable trace timeline.

### Phase 5 — Policy engine & scoring
- [ ] Design the policy YAML schema (rules with id, description, severity, check type, EU-AI-Act tag).
- [ ] Implement rule primitives: `tool_never_called`, `secret_not_in_output`, `no_external_send_of(pii)`, regex asserts, span-sequence asserts.
- [ ] Implement optional **LLM-as-judge** rule with a rubric + self-consistency (majority vote), clearly separated from deterministic rules.
- [ ] Aggregate → per-rule pass/fail + severity + overall score.
- [ ] Ship a default `policy.yaml` mapping rules to EU AI Act and NIST AI RMF themes.
- [ ] Snapshot tests on scoring against fixture traces.
- **DoD:** a trace + policy → deterministic, explainable score with per-rule reasons.

### Phase 6 — Signed report
- [ ] `report/schema.py`: run metadata + scenario results + trace refs + policy version + input hashes.
- [ ] ML-DSA `signing.py` + `verify`; canonical JSON.
- [ ] `render.py`: HTML report — scenario heatmap, failed-rule detail, trace excerpts.
- [ ] CLI `agentshield verify report.json`.
- [ ] Round-trip + tamper tests.
- **DoD:** signed report verifies; mutation fails; HTML is reviewer-readable.

### Phase 7 — Service + persistence
- [ ] FastAPI app; `/health`, `/version`.
- [ ] Models: `AuditRun`, `ScenarioResult`, `TraceRef`; Alembic migration.
- [ ] Endpoints: enqueue run, get status, fetch report, **diff two runs**.
- [ ] Async worker executing suites off-request; status lifecycle.
- [ ] Integration tests with a Postgres container.
- **DoD:** submit → poll → fetch signed report over HTTP.

### Phase 8 — Dashboard
- [ ] React scaffold; typed API client from OpenAPI export.
- [ ] Runs list; run detail with **scenario heatmap** (suite × outcome).
- [ ] **Trace timeline** component (llm/tool spans, expandable).
- [ ] **Version diff** view: regression across agent/model versions (the headline feature).
- [ ] Loading/empty/error states; deploy with a public demo link.
- **DoD:** a reviewer explores a full audit visually without the CLI.

### Phase 9 — GitHub Action (deploy gate)
- [ ] `action.yml` Docker action wrapping the CLI; inputs: agent entrypoint, suites, policy, thresholds.
- [ ] Non-zero exit on regression/threshold breach; markdown step-summary of failures.
- [ ] Self-test workflow running the Action against `examples/` agent.
- [ ] `docs/quickstart.md` copy-paste snippet.
- **DoD:** a deliberately-weakened example agent fails the gate in CI.

### Phase 10 — Benchmark, release, write-up
- [ ] Run the full suite against **5 open models** via `litellm`; collect pass rates.
- [ ] Publish a `RESULTS.md` leaderboard table.
- [ ] Dockerfile (multi-stage, non-root) + compose for the full stack.
- [ ] Tag `v0.1.0`; publish to PyPI (Test PyPI first); signed release notes.
- [ ] Record a 3-minute demo and publish a short results write-up.
- **DoD:** `pip install agentshield`, run quickstart, reproduce a signed report; results table published.

---

## 5. Definition of done (whole project)
- One command runs the full stack; `pip install agentshield` works clean.
- ≥20 adversarial scenarios across 5 categories; ≥5 models benchmarked.
- Signed, verifiable, diff-able reports; public dashboard.
- The Action gates a demo PR; CI green; mypy strict; coverage ≥80%.
- A published results table and a short results write-up.

## 6. Stretch goals
- Multi-turn scenarios where a follow-up task adapts to the policy the agent was given.
- Cost and latency per model as a second axis on the results table.
- A plugin API so other people can ship scenario suites, and a public registry of those suites.
- An MCP-server adapter for agents whose tools are MCP tools.

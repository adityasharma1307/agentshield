# Service

The `service` extra is an HTTP API. A client submits a run and polls it. The suite runs in a worker. The request that accepts the run does not execute it.

```bash
python -m pip install -e ".[service]"
```

Apply the migrations before the first request that uses the database. The process does not migrate on startup.

```python
from agentshield.service.db import upgrade_database

upgrade_database("sqlite:///agentshield.db")
```

## Routes

| Method | Path | Result |
| --- | --- | --- |
| `GET` | `/health` | `{"status": "ok"}`. Does not open the database. |
| `GET` | `/version` | The package version. Does not open the database. |
| `POST` | `/runs` | `202` and `{"id", "status": "queued"}`. Body fields are `suite` (a directory), `agent` (`module:attribute`), and `policy` (a file). `403` when the agent or a path is not allowlisted (see below). |
| `GET` | `/runs` | Newest runs first. Each row has id, status, time, agent, and how many scenarios passed. |
| `GET` | `/runs/{id}` | `queued`, `running`, `succeeded`, or `failed`. |
| `GET` | `/runs/{id}/report` | The signed report when the status is `succeeded`. Otherwise `409`. |
| `GET` | `/runs/{id}/traces` | Ordered trace events for each scenario when the status is `succeeded`. Otherwise `409`. |
| `GET` | `/runs/{id}/diff/{other_id}` | Scenario ids whose pass/fail differs, with a severity. `409` when the two runs do not share a suite hash. |

The report signature is HMAC, algorithm `local`. It is not ML-DSA. The key comes from `AGENTSHIELD_SIGNING_SECRET`, or from a file named by `AGENTSHIELD_SIGNING_SECRET_FILE`, and there is no default. The file must be mode 0600 or 0400, owned by the worker's user or root, and not a symlink. Without it, or with a key shorter than 32 bytes or the old `agentshield-local-dev` value, the API and the worker refuse to start. Generate one with `openssl rand -hex 32`.

The worker reads the key and deletes it from its environment. Only the signer keeps it. The agent runs in a child process with no `AGENTSHIELD_*` variables. On Linux the worker also marks itself non-dumpable, so a child running as the same user can't read the key from `/proc/<worker>/environ` or from the worker's memory. That still leaves files the worker's user can read, so set `AGENTSHIELD_AGENT_USER` (a name or uid, plus optional `AGENTSHIELD_AGENT_GROUP`). The worker then starts each agent as that user, with no supplementary groups. It needs root or CAP_SETUID and CAP_SETGID to do that. If the user is unknown, is root, is the worker's own user, or can't be applied, the worker refuses to start or to run the agent.

`docker/compose.yaml` does this for you. The image has an `agent` user. The key is a Docker secret at `/run/secrets/signing_key`, and on the host it's a root-owned 0600 file (see the comment at the top of the file). The API and the worker run as root with every capability dropped, except SETUID and SETGID on the worker, and the worker runs agents as `agent`. Root on the host, or in those containers, can still read the key.

The signed report stores a sha256 of each scenario trace. The service database also stores the trace JSON so the dashboard can show arguments and results.

## What a run may name

A run imports `agent` as code and reads `suite` and `policy` from disk, so `POST /runs` checks both against an allowlist before it stores anything:

- `AGENTSHIELD_ALLOWED_AGENTS`: comma-separated. An entry is an exact `module:attribute` or `package.*`. Unset or empty allows no agent, so a fresh service answers `403` until you name one.
- `AGENTSHIELD_ALLOWED_ROOTS`: directories separated by `os.pathsep`. `suite` and `policy` must resolve (symlinks followed) inside one of them. Unset means the installed `agentshield` package, which holds the shipped suites and the default policy.

`create_app(allowlist=RunAllowlist(...))` sets the same thing in code. The API has no authentication of its own; keep it on a loopback or private interface.

## Docker Compose

`docker/compose.yaml` needs `POSTGRES_PASSWORD` and `REDIS_PASSWORD` in the environment; there are no defaults, and compose refuses to start without them. Postgres and Redis publish no host ports. The API publishes `127.0.0.1:8000` only, and Jaeger (debug profile) publishes its ports on `127.0.0.1` only.

## Worker

`create_app()` keeps accepted run ids in memory unless `AGENTSHIELD_REDIS_URL` is set. With that variable set, the app publishes `execute_run` to Redis. A separate process runs the job:

```bash
arq agentshield.service.worker.WorkerSettings
uvicorn agentshield.service.app:create_app --factory
```

`AGENTSHIELD_DATABASE_URL` selects the database for both processes. The default is `sqlite:///agentshield.db`. The default CI tests use SQLite. A Postgres upgrade test runs when `AGENTSHIELD_TEST_DATABASE_URL` is set. CI does not start Postgres.

On a worker exception the run status is `failed`. The stored error is the exception text with environment values removed.

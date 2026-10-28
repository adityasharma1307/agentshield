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

The report signature is HMAC, algorithm `local`. It is not ML-DSA. The key comes from `AGENTSHIELD_SIGNING_SECRET`, and there is no default. Without it, or with a key shorter than 32 bytes or the old `agentshield-local-dev` value, the API and the worker refuse to start.

### Generating a key

Generate the key; don't type one:

```bash
export AGENTSHIELD_SIGNING_SECRET="$(openssl rand -hex 32)"
# or
export AGENTSHIELD_SIGNING_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

Either gives 64 hex characters (256 random bits). Store it in your secret manager and pass it to the API and the worker. `agentshield verify --key` needs the same bytes in a file (`printf %s "$AGENTSHIELD_SIGNING_SECRET" > key.bin`).

Agentshield also refuses a key of 32 bytes or more that looks hand-made: under about 80 bits by byte frequency, mostly runs of equal or adjacent characters (`aaaa`, `abcd`), or an 8-character stretch that repeats (`password-password-…`). These checks catch typed patterns. They can't catch a long passphrase of distinct words, so use a generated key.

The worker reads the key and deletes it from its environment. Only the signer keeps it. The agent runs in a child process with no `AGENTSHIELD_*` variables. On Linux the worker also marks itself non-dumpable, so a child running as the same user can't read the key from `/proc/<worker>/environ` or from the worker's memory. That doesn't stop root, or an agent that can read the files the key came from. For a hostile agent, start the worker as root with `AGENTSHIELD_AGENT_USER` set to an unprivileged account that can run the interpreter. The agent child then gets that uid, and the report says `agent uid separate`. Otherwise run the agent in its own container.

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

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
| `POST` | `/runs` | `202` and `{"id", "status": "queued"}`. Body fields are `suite` (a directory), `agent` (`module:attribute`), and `policy` (a file). |
| `GET` | `/runs` | Newest runs first. Each row has id, status, time, agent, and how many scenarios passed. |
| `GET` | `/runs/{id}` | `queued`, `running`, `succeeded`, or `failed`. |
| `GET` | `/runs/{id}/report` | The signed report when the status is `succeeded`. Otherwise `409`. |
| `GET` | `/runs/{id}/traces` | Ordered trace events for each scenario when the status is `succeeded`. Otherwise `409`. |
| `GET` | `/runs/{id}/diff/{other_id}` | Scenario ids whose pass/fail differs, with a severity. `409` when the two runs do not share a suite hash. |

The report signature is HMAC, algorithm `local`. It is not ML-DSA. `AGENTSHIELD_SIGNING_SECRET` is the key when it is set. The default key is for local development.

The signed report stores a sha256 of each scenario trace. The service database also stores the trace JSON so the dashboard can show arguments and results.

## Worker

`create_app()` keeps accepted run ids in memory unless `AGENTSHIELD_REDIS_URL` is set. With that variable set, the app publishes `execute_run` to Redis. A separate process runs the job:

```bash
arq agentshield.service.worker.WorkerSettings
uvicorn agentshield.service.app:create_app --factory
```

`AGENTSHIELD_DATABASE_URL` selects the database for both processes. The default is `sqlite:///agentshield.db`. The default CI tests use SQLite. A Postgres upgrade test runs when `AGENTSHIELD_TEST_DATABASE_URL` is set. CI does not start Postgres.

On a worker exception the run status is `failed`. The stored error is the exception text with environment values removed.

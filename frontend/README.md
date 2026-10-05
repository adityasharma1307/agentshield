# Agentshield dashboard

Reviewer UI for a finished audit. It talks to the service through a generated client (`src/api/schema.d.ts`), produced from `openapi.json`. Do not hand-write a second client. Regenerate with `npm run generate-api` after the service routes change. Export a fresh `openapi.json` from `create_app(database=False).openapi()` first.

## Two commands

From the repository root, with the `service` extra installed and the database migrated:

```bash
uvicorn agentshield.service.app:create_app --factory --port 8000
```

From `frontend/`:

```bash
npm run dev
```

The dev server proxies `/api` to `http://127.0.0.1:8000` and removes the `/api` prefix. Page routes such as `/runs/:id` stay in the browser. Open the printed local URL. The runs list, a run heatmap, the trace, and the compare view are there.

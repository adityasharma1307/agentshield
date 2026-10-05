# Dashboard

The reviewer UI lives in `frontend/`. It is a Vite, React, and TypeScript app. The API client is generated from the service OpenAPI document. `frontend/README.md` has the two commands that start it.

From a checkout, with the service already running on port 8000:

```bash
cd frontend
npm run dev
```

The runs list shows id, status, time, and how many scenarios passed. A run opens a heatmap with suites as rows and scenarios as columns. Pass and fail are written in the cell. The trace lists events in order. A tool call expands to its arguments and result, and a long value can be expanded. Compare asks for two runs and lists the scenario ids whose outcome changed.

There is no public demo deployment.

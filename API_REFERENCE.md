# ForgeOS API Reference

The FastAPI backend is the authoritative source for the root Hami dashboard.
For local direct requests, use `http://127.0.0.1:8000` (API docs:
`http://127.0.0.1:8000/docs`). The Vite development server proxies the same
`/api/*` paths to the configured local backend; Vercel routes those same-origin
paths to the FastAPI service.

The local proxy target defaults to port 8000. Set `FORGEOS_API_TARGET` when
starting Vite if the backend listens elsewhere. The root frontend no longer
hosts an in-memory API or supplies demo records.

## Read endpoints used by the dashboard

All of these endpoints are `GET` requests and have `/api` aliases:

| API path | Returned data |
| --- | --- |
| `/health` | Backend readiness and database availability |
| `/ai/status` | Configured AI provider status |
| `/stats` | Total signals, patterns, opportunities, and experiments |
| `/observer/stats` | Observation counts, quality counts, real outcomes, and verified revenue |
| `/signals` | Stored observations and Observer-assigned metadata |
| `/opportunities` | Stored opportunities, status, and explicitly estimated fields |
| `/forge/beliefs` | Current persisted beliefs and linked supporting signal IDs |
| `/forge/decisions` | Decision records |
| `/forge/execution/actions` | Action records, policy result, and approval state |
| `/forge/outcomes` | Recorded outcomes, with `data_scope` and a REAL/SANDBOX label |
| `/workers` | Persisted worker-task records |
| `/forge/cycles` | Persisted cycle history |
| `/forge/experiments` | Persisted experiment records |
| `/forge/money/revenue-breakdown` | Potential, expected, and realized values as separate fields |

Example:

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/signals
curl http://127.0.0.1:8000/api/forge/outcomes
```

The root UI fetches these paths through same-origin `/api` and rejects
non-2xx, non-JSON, or unexpected response shapes. Backend and database errors
are shown in the dashboard; an empty response is rendered as empty rather than
filled with sample content.

## Recording an observation

The Signals tab uses the canonical `POST /signals` endpoint (also available at
`POST /api/signals`) with this payload:

```json
{
  "content": "The observation as recorded",
  "source": "manual"
}
```

The backend stores the observation and returns its own Observer metadata.
Submitting a statement does not independently verify it, create a customer,
establish demand, or record revenue. The UI does not call cycle, collector,
discovery, decision, action, or outcome mutation endpoints.

## Evidence and metric semantics

- Opportunity revenue/cost fields are estimates, never actual revenue.
- Decision, action, and outcome records remain separate. A ready action does
  not prove execution.
- Outcome responses preserve their canonical `data_scope`; SANDBOX/TEST data
  is not presented as REAL evidence.
- `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT MEASURABLE** until there
  is verified real-transaction evidence. A missing value is not rendered as a
  measured zero.

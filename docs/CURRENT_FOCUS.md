# Current focus — verified system state and the next owner-gated step

**Architecture authority:** [`FORGE_SUBSTRATE_BLUEPRINT.md`](../FORGE_SUBSTRATE_BLUEPRINT.md)
**Claim ledger:** [`CAPABILITY_QUEUE.md`](CAPABILITY_QUEUE.md)
**Work order:** serial; claim → build → test → integrate → verify → record.

## Verified 2026-09-30 (full reinspection pass)

The Vercel API ingress failure recorded here on 2026-09-26 is resolved in
production. Re-verified with read-only requests, not inferred from the fix:

| Check | Observed 2026-09-30 |
| --- | --- |
| `GET /api/health` | HTTP 200, `status=ok`, `database.driver=postgresql`, `url_configured=true`, `available=true`, `cron_secret_configured=true`, `readiness.ready=true` |
| `GET /api/public/feed?limit=1` | HTTP 200 with feed JSON |
| `GET /api/public/providers` | HTTP 200 `[]` — no provider has published a listing |
| `GET /api/public/services` | HTTP 200 |
| `GET /api/public/discoveries?limit=2` | HTTP 200, Crossref-derived items |
| `GET /api/public/trust/provider/1` | HTTP 404 `provider not found or not publicly verified` (expected) |

One production surface was unreachable and is now repaired in code: only
`/api/*` reaches the Python service, so the machine-readable contract could not
be read in production (`/openapi.json` answered the frontend HTML,
`/api/openapi.json` answered 404) even though the document generates fine.
`/api/openapi.json` now aliases the schema; verified on the reloaded local
service (200 `application/json`, identical to `/openapi.json`) and covered by
tests, and it becomes readable in production on the next deploy.

Local baselines on the same date: `cd backend && pytest tests -q` → 540
passed, 2 skipped, and **549 passed, 2 skipped** after the repairs recorded in
[`CAPABILITY_QUEUE.md`](CAPABILITY_QUEUE.md) added 5 recovery-drill tests and 4
API-ingress tests; `npm run typecheck` clean; `npm run build` produced
`.vercel/output`; `npm test` → 70 passed; `scripts.truth_audit_report` →
`integrity=ok`, zero anomalies; `scripts.recovery_verify` → the snapshot
restores to 66 tables / 54,625 rows with per-table counts equal to the live
file, no foreign-key violations, no stale rebuild tables.

None of that is commercial evidence. There is no opportunity, product,
customer, outcome, payment, or revenue row from a real transaction, so
`OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE** (not
zero). The public feed is derived from scholarly/metadata sources and carries
an explicitly uncorroborated hypothesis; it is not buyer demand.

## Open gates (owner action)

1. `docs/PUBLICITY_GATE.md` stays **OPEN**: the footer domain is
   `Domain pending verification`, the contact mailbox is a placeholder, and no
   publicity or outreach is authorized.
2. A real conversation must produce a real need through the existing intake.
   `POST /signals/public-request` is verified working end-to-end: HTTP 202,
   signal stored as `user_request`/`user_submitted`, the demand-understanding
   task completed as `possible_demand` with its unresolved questions preserved,
   the same `Idempotency-Key` returned the same signal with no duplicate, and
   the request did not appear in the public feed.
3. Commercial discovery stays blocked: `source_clearance_registry` has no
   `authorized_prospect_discovery` entry, so no prospect source may be
   queried.

## Next removable dependency (local environment, not commercial)

The newest local cycle is from 2026-09-24, so the local substrate projections
behind current code have never run here: `storage/forge.db` holds 1 substrate
entity and 0 relations. A verified cycle on a copy of that same file produced
949 canonical entities and 3,314 relations with **zero duplicates** and zero
stage errors, so this is local progress, not a code defect. Advancing it is
the owner's call, since it is a long-running process they start:

```bash
cd backend && ../.venv/bin/python -m scripts.scheduler --every 1800
```

Second local-environment item: the legacy Next cockpit currently holds port
8080, which the public app's dev server also requires (`strictPort`), so
`npm run dev` for the public site cannot start while the cockpit is up. Both
are recorded in `docs/CAPABILITY_QUEUE.md`; neither changes an approval,
permission, or execution step on the commercial path.

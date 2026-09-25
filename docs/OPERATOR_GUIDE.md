# ForgeOS personal pilot operator guide

Verified development checkpoint: September 14, 2026 (Nepal time).
**Real revenue $0; real customers 0; external customer validation 0.**
This is local pilot software, not evidence of a successful business. Earlier reports
and historical database summaries are not current commercial-readiness claims.

## 1. Start locally or with containers

The canonical host database is the absolute `<ForgeOS>/storage/forge.db`. Native
startup exports that URL before changing directories. Containers see the same host
file only as `/app/storage/forge.db` through the single `./storage:/app/storage` bind
mount. `backend/app/database.py` rejects relative SQLite URLs so path drift fails
loudly instead of creating a second database.

### Docker Compose (preferred deployment baseline)

```sh
cp backend/.env.example backend/.env   # optional settings; do not put DATABASE_URL here
docker compose build
docker compose --profile verify run --rm backend-tests
docker compose build frontend
docker compose up -d
docker compose logs backend | grep "resolved SQLite path"
# Expected inside the backend container: /app/storage/forge.db
```

The backend image installs dependencies with `pip install --target /app/backend/.deps`
and sets `PYTHONPATH` explicitly. The production frontend image uses the committed
Bun lockfile, runs `bun install --frozen-lockfile`, builds Next.js, and starts the
production server. The worker is an explicit profile: `docker compose --profile worker up -d`.
Run exactly one scheduler/worker for a given SQLite volume.

### Constrained native mode

Prerequisites: Python 3.11+ and Bun 1.3+.

```sh
./start.sh
# or verify manually:
cd backend
python3 -m pip install --target .deps -r requirements.txt
PYTHONPATH="$PWD/.deps:$PWD" python3 -m pytest tests/ -q
cd ../frontend
bun install --frozen-lockfile
bun run build
```

No virtual environment or global Python install is required. `AI_PROVIDER=mock` and
hash embeddings remain offline and cost-free after dependencies are installed.
Open `http://localhost:3000`; API documentation is at `http://localhost:8000/docs`.

## 2. First human experiment — canonical workflow

1. Submit genuine source text on the Analyze page / `POST /observer/observe` with
   JSON `{"content":"actual observation", "source":"manual"}`. Preserve who/where/when
   in the text. The observer records signal provenance and evidence, not proof of
   the truth of every claim.
2. Run `POST /forge/cycle` (or the existing Run Cycle UI). The existing pattern,
   belief/evidence, economic discovery and decision services prepare work.
3. Open **Flow**. Select **REAL** only for real observations. Read target customer,
   source/economic evidence, hypothesis, questions, decision rationale, and risks.
4. Prepare validation if absent. Configure assumptions before approval through:
   `POST /orchestrate/ID/advance?x_interviews=10&y_confirm=5&z_willing=3&price_assumption=99&time_window=72%20hours`.
   These are **operator assumptions**, not empirically proven thresholds. To change
   an already-started experiment, preserve its history rather than overwriting it.
5. **Approve** authorizes the human task. It does not email, interview, or charge
   anybody. ForgeOS cannot invent responses. A policy-blocked action cannot be approved.
6. You contact real target customers, ask the displayed questions, and collect
   actual answers. Click **Execute human task** to attest that the human work was
   carried out. This only moves the task to **OUTCOME_PENDING**.
7. **Record validation outcome**: enter the actual narrative, success `true`, `false`
   or blank, and the number expressing willingness to pay (not paid conversions).
   Contacts JSON uses this shape, with actual people/businesses only:

```json
[{"name":"Actual shop name","identifier":"operator's reference","segment":"repair shop","stage":"interested","notes":"confirmed no-show problem; reported willingness to pay $40"}]
```

   Do not paste imaginary people in REAL mode. Allowed stages: lead, contacted,
   interested, paid_customer, churned. `success=false` can mean rejection of the
   original price even if lower-price demand exists. Notes should explain this.
8. Outcome, measurement, learning event, lesson provenance, and contact records
   commit together. Failed writes roll back together. Exact retries reuse the
   outcome; conflicting retries are rejected instead of rewriting history.
9. Click **Next decision**. Price feedback (e.g. an explicitly configured $99 test
   rejected in favor of $40) creates a price-sensitivity lesson and changes the
   recommendation to test the lower price. This is deterministic scoped recall,
   not an assertion that an AI independently verified customers.
10. **Create gated product** checks distinct named contacts linked to recorded
    ACTUAL_RESPONSE outcomes. Default gate: five confirm pain, three show interest,
    with a completed experiment's willingness count. Duplicated events do not
    become additional customers. API gate thresholds are configurable assumptions.
    Target/offer derive from the originating opportunity, not generic placeholders.
    Created offers are **validating**, **not_launched**. A score alone never launches.
11. **Commercial actions** creates a channel, records customer events, and separately
    records actual collected USD revenue with a source and evidence description.
    A lead, interested person, paid_customer event, or willingness quote is NOT cash.
12. Cash creates an explicit ACTUAL_REVENUE outcome and another product-linked
    learning event/lesson. Check the selected scope's product totals. Unique payment
    idempotency keys protect retries; use a new key only for a genuinely new payment.

## 3. Lifecycle and scope

Canonical actionable unit: existing `Experiment`, not an additional engine.
Stored states remain planned → ready → in_progress → completed, plus blocked or
abandoned. Flow derives PROPOSED / APPROVAL_REQUIRED / EXECUTABLE / OUTCOME_PENDING /
LEARNED. Execution completion is not business success. `Action` remains a legacy API.

**SANDBOX requires a separate database as well as downstream SANDBOX labels.**
Signals, patterns, beliefs, sources and opportunities are shared discovery models;
they do not have full multi-tenant scope isolation. Never seed hypothetical source
text into your real working database. Stop writers and copy the DB for practice,
then set an absolute `DATABASE_URL` BEFORE starting a new backend process. On a
sandbox copy, call `/forge/cycle?data_scope=SANDBOX` and select SANDBOX in Flow.
    A scope selector does not create a separate database for you.

## 2A. Truth & Reality dashboard

The dashboard intentionally separates **database volume** from knowledge gained
from reality. “Raw signals” includes historical and bulk-ingested observations;
it is not a count of verified facts. Evidence is provenance-linked source
material, not truth. Patterns are inferences. Opportunities are hypotheses until
human validation occurs. The Truth & Reality panel reports, separately:

- raw, observed, collected, and duplicate signal counts;
- inferred patterns and opportunity hypotheses;
- verified claims and human-validated problems;
- REAL experiments, REAL outcomes, REAL learning events, and REAL revenue.

The application preserves historical records rather than deleting them to improve
the dashboard. On startup and runtime inspection, abandoned cycle records that
remain `RUNNING` beyond the recovery window are reconciled to `FAILED` with a
reason and end timestamp. This preserves the audit trail while ensuring the
current running count reflects current operations.

Tests use isolated databases. `$99` fixture revenue and `$40` fixture willingness
are **SANDBOX/TEST only**. No such payment exists in the included source database.
REAL aggregates exclude SANDBOX. All payment reports are operator-reported,
not independently bank-verified. Dollar cash input supports USD only; other
currencies are rejected rather than silently converted. Estimates/expected value/
potential 30/90-day values are not collected revenue or a valuation of ForgeOS.

## 4. AI configuration

Default: `AI_PROVIDER=mock`, `EMBEDDING_PROVIDER=hash`, no keys/cost.
Mock uses deterministic heuristics/templates, not validated external facts.
For local AI install Ollama separately, download your chosen model, and set
`AI_PROVIDER=ollama`, `OLLAMA_HOST`, `OLLAMA_MODEL` in backend `.env`.
Optional OpenAI requires `requirements-optional.txt` and a locally stored key.
Real-provider failure is fail-closed by default (`AI_FALLBACK_TO_MOCK=false`).
Do not describe fallback output as model-verified customer evidence.

## 4A. Real-world integration policy

ForgeOS is **offline-first**. The local database, deterministic scoring,
operator-entered human outcomes, backups, and mock/hash providers remain usable
when the network, an external API, or a model provider is unavailable. External
services are optional adapters, never the source of truth and never a prerequisite
for starting the application.

When an external integration is added, it must have a local durable record of the
request, response/provenance, status, retry count, and last error. Calls must use
timeouts, bounded exponential backoff, idempotency keys where supported, and a
fail-closed path that leaves the operator with a recoverable local task. Never
convert an API response into a verified customer claim or actual revenue without
human or payment evidence. This policy applies to AI providers, research sources,
CRM/email tools, payment providers, analytics, and future webhooks.

## 5. Scheduler, logs and backups

```sh
cd backend
python -m scripts.scheduler --help
python -m scripts.scheduler --every 3600 --backup-every 21600 --backup-keep 10
# A one-off canonical cycle:
python -m scripts.run_daily_cycle
```

Use one scheduler for a given DB. It calls existing `run_daily_cycle.run_once()`;
it does not implement a competing intelligence engine. Default log locations:
`logs/daily_cycle_log.jsonl`, `storage/scheduler.log`, and DB `cycle_runs` records.
Backups: `storage/backups/*.db.gz` using SQLite VACUUM INTO, gzip, restore integrity
validation, then retention. `safe_backup()` returns the actual gzip path.
Retention must be at least one. Never delete the working database to test recovery.

On Vercel, `vercel.json` invokes the same runner once daily through
`/api/scheduled/cycle`. The endpoint requires a `CRON_SECRET` environment
variable and an exact `Authorization: Bearer …` header; it returns 503 until
that secret is configured. Vercel sends the header automatically for cron
invocations when `CRON_SECRET` is set. The deployment must use the durable
`DATABASE_URL`; Vercel's `/tmp` SQLite fallback is not a persistent world of
record. The daily schedule is compatible with Hobby plan limits. It runs one
bounded cycle per day, not a continuously resident process.

Manual verified snapshot:

```sh
cd backend
python -c 'from app.services.backup import safe_backup; print(safe_backup(keep=10))'
```

Restore procedure: stop backend and scheduler; preserve current database separately;
decompress a selected snapshot into a NEW file; run `PRAGMA integrity_check` using
Python sqlite3; start backend with `DATABASE_URL` pointing to that file; inspect
counts/flow before switching. Startup reruns additive migrations safely.

Cycle failures roll back the current transaction and log failure; earlier committed
discovery stages remain historical records (the entire cycle is not one transaction).
Next ticks can run. A timed-out Python thread cannot safely be forcibly killed; the
scheduler logs the timeout but keeps overlap protection until it finishes. On Unix
`fcntl` additionally guards scheduler processes. Other platforms only get local
thread protection: run one instance. If the worker truly hangs, stop the process,
check provider/network/filesystem, restore a verified backup if needed, restart.

## 6. Security and deployment boundary

Bind loopback only. `FORGE_API_KEY` is optional and protects writes, **not reads**.
Flow accepts a session-only key and sends X-API-Key; refreshing the page clears it.
Never store real keys in repository or ZIP. Query-string key compatibility is legacy;
prefer headers because URLs may appear in logs. CORS permits localhost:3000 by default.
This is NOT multi-user authentication, tenant isolation, encryption at rest, hosted
billing, or a hardened public SaaS. Do not expose it publicly without those controls.
Security-audited dependency pins were updated and regression-tested; an audit is a
point-in-time known-vulnerability check, not a guarantee of security.

## 7. Tests and recovery checks

```sh
cd backend
python3 -m pip install --target .deps -r requirements.txt
PYTHONPATH="$PWD/.deps:$PWD" python3 -m pytest tests/ -q
PYTHONPATH="$PWD/.deps:$PWD" python3 -m compileall -q app
cd ../frontend
bun install --frozen-lockfile
bun run build
```

The authoritative HTTP fixture starts with realistic SANDBOX repair-shop source
text, then invokes actual observer/cycle/orchestrator services. It does not insert
every intermediate stage by hand. Human responses/payments are synthetic inputs.
See root `STATUS.md`, `COMPLETION_REPORT.md`, and `verification/` for exact evidence.

## 8. Known boundaries before a real pilot

- A human still must contact customers, deliver an actual service, collect money,
  and supply genuine external evidence. No test proves those happened.
- Source quality and scoring are heuristics, not verified market research.
- Legacy noisy opportunities and original inflated summaries are preserved as
  historical data; current ranking deprioritizes low-quality text without deletion.
- Product/channel funnel metrics are event counts unless explicitly named unique;
  they are not independent evidence of paying customers. Revenue is explicit ledger only.
- Sequential retries are covered; no claim of distributed/concurrent exactly-once
  delivery or multi-writer high-load readiness.
- Windows/macOS startup and Docker runtime were not executed in this Linux container.
- Automated browser click-through was unavailable locally (missing Chromium).
  TypeScript, production build, HTTP endpoints and clean extraction are verified;
  the first pilot must include the operator's browser walkthrough.

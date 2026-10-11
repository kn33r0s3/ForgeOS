# Hami — product and system entrypoint

**Current snapshot:** 2026-10-11 (Nepal time) · branch `main` · deployed commit `27cb0a9`.

**Production web surface:** [https://haminp.vercel.app](https://haminp.vercel.app). Vercel currently reports the deployment for this commit as READY and lists the Hami alias. A deployment/build status does not by itself verify API readiness, durable production persistence, scheduled jobs, real users, or economic outcomes.

Hami is the product identity. This repository is the in-place technical lineage evolving from ForgeOS; historical API paths, database records, environment variables, imports, and migration identifiers remain compatible unless a specific migration proves safe. There is one Hami application, not a replacement frontend, parallel service catalogue, or second architecture.

## Canonical Hami system map

- [System map and integration rules](docs/HAMI_SYSTEM_MAP.md) describes the two connected flows, route states, security boundaries and acceptance rule for future work.
- [Feature/route registry](features.json) tracks every page and the registered public APIs with an explicit `live`, `hidden`, `archived` or `planned` state. Its schema is published at [public/features.schema.json](public/features.schema.json).
- `src/lib/hami-system.ts` is the single source for top navigation, footer groups, contextual page pathways and required public routes. The header/footer no longer keep separate competing route lists.
- `src/components/layout/hami-pathways.tsx` connects related evidence, questions, experiments, opportunities, actions, services, provider records and work pages.
- `public/sitemap.xml` includes only indexable, live public destinations. Owner controls, closed intake, TEST-only demos, archived redirects and pages marked `noindex` are intentionally omitted from public discovery.

**Current registry snapshot:** 36 entries — 25 live, 7 hidden, 4 archived, 0 planned. Hidden means retained but not advertised (owner-only, TEST-only or closed); it does not mean delete. Archived routes remain compatibility redirects rather than parallel features.

## Commercial and authorization truth

`docs/REVENUE_LOG.md` currently contains no commercial evidence entries. No customer, booking, payment or revenue claim follows from a page, passing test, deployed endpoint or intelligence cycle. Report `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` as **NOT MEASURABLE** until a real qualifying transaction is independently evidenced.

The online contact/request path and Forge Bot intake remain closed; a public request is not a booking or permission to contact someone. No automatic outreach, consequential action or payment collection is enabled by navigation integration. Do not claim willingness to pay, a selected seller, a verified merchant route or real revenue without the corresponding owner authorization and evidence.

The first pilot remains outcome-oriented: owner-run discovery → one real customer → one real paid outcome → repeat → automate → scale. No category, fee, or willingness to pay is assumed. The $249 Hami Revenue Operator remains a later-stage offer after demonstrated value. New paid software and infrastructure remain off-limits before first real revenue unless a verified critical need justifies them.

## Engineering invariant

**Drive owner dependency to zero**: prioritize fewer owner actions per verified real economic outcome, not endpoint count or internal activity. Every change should state the owner action it removes, what remains, and the next evidenced dependency. Preserve authorization, privacy and evidence boundaries; see [AGENTS.md](AGENTS.md). A successful intelligence cycle or an allowed policy decision is not itself an economic outcome or autonomous execution.

Current status and historical run results are tracked in [STATUS.md](STATUS.md), [docs/REVENUE_LOG.md](docs/REVENUE_LOG.md), [docs/CAPABILITY_QUEUE.md](docs/CAPABILITY_QUEUE.md), and [docs/archive/status-reports/STATUS-history.md](docs/archive/status-reports/STATUS-history.md).

---

## What Hami is

Hami is not a scoring SaaS or a leaderboard of business ideas. It evolves the
existing ForgeOS system rather than creating a parallel architecture.

It is a system organized around:

```
OBSERVE → VERIFY → UNDERSTAND → DECIDE → ACT → MEASURE → LEARN → repeat
```

Intelligence emerges from the full evidence → reasoning → decision → action → outcome → learning loop — not from an LLM or a heuristic score alone.

---

## Core domain model

Observation → Evidence → Pattern → Hypothesis/Belief → Opportunity  
→ Decision → Strategy → Action → Experiment → Outcome → Measurement → Learning  
→ Belief/strategy update

Every important claim can answer:
- What do we know?
- What do we think?
- How do we know?
- What contradicts it?
- What don’t we know?
- What should we do to find out?

Knowledge is labeled: **OBSERVED / INFERRED / ESTIMATED / UNKNOWN / ACTUAL**.

---

## Quick Start

The root Vite app is the current Hami web interface, matching the frontend
deployed at `haminp.vercel.app`. Start it with the existing development
command:

```bash
npm run dev
```

- Hami web app: http://localhost:8080
- API docs: http://localhost:8000/docs (when the backend is running)

The Vite development server proxies same-origin `/api` requests to the local
FastAPI backend at `http://127.0.0.1:8000` by default. To use a backend on a
different local port, set `FORGEOS_API_TARGET` when starting the app, for
example `FORGEOS_API_TARGET=http://127.0.0.1:8100 npm run dev`. The frontend
does not provide mock API records; if the backend is unavailable, it shows the
connection error rather than sample data.

`./start.sh` starts the native backend, scheduler, and root web app together.
The task worker is disabled by default; enable deliberately with
`FORGEOS_ENABLE_WORKER=true ./start.sh`. Stop that combined stack with
`./stop.sh`.

The optional Docker Compose frontend on port 3000 is the archived legacy
Next.js dashboard at `docs/archive/legacy-frontend/`; it is not the current
Hami web app.

### Production frontend/API configuration

The current public Forge app is the root Vite service. Its browser client uses the same-origin `/api` path, which Vercel routes to the FastAPI service declared in `vercel.json`; do not point it at `localhost` or `127.0.0.1`. The API service owns the `/api` aliases and receives the original request path.

The separate `docs/archive/legacy-frontend/` Next.js dashboard is a
legacy/local app. If it is run independently against another backend, its
client may use:

```bash
NEXT_PUBLIC_API_URL=https://<actual-production-backend>
```

That variable is not required by the current root Vite service. Production API health must be checked at `/api/health`; local build success alone does not establish deployment health.

---

## Architecture (backend)

| Layer | Role |
|-------|------|
| Observer + Collectors | Normalized observations with provenance |
| Signal quality | Concreteness, coherence, duplication gates |
| Pattern engine | Repeated problems from real signals |
| Belief + Evidence | Hypotheses with supporting/contradicting evidence |
| Reality checker / memory | Confidence drift, predictions, source reliability |
| Opportunity engine | Downstream of evidence; heuristic scores labeled as such |
| Economic intelligence | ESTIMATED vs ACTUAL revenue/cost separation |
| Decision engine | Explicit rationale, alternatives, expected outcomes |
| Autonomy / policy | ALLOW / REQUIRE_APPROVAL / BLOCK |
| Execution engine | Action lifecycle (never silent success) |
| Experiment runners | Belief tests + opportunity tests |
| Learning engine | Expected vs actual → structured LearningEvents → belief updates |
| Forge loop + worker | Full cycle orchestration |

NEPSE / paper trading / stock prediction: **removed and not restored**.

---

## Manual Analyze flow

Input: *“Restaurants still take orders on paper.”*

Output is structured intelligence, not only scores:
- Observation stored (user report, provenance)
- Opportunity with **HEURISTIC** score
- Explicit unknowns (willingness to pay, market size, …)
- Recommended next experiment
- Proposed Decision for low-cost validation

---

## Tests

```bash
cd backend
python3 -m pip install --target .deps -r requirements.txt
PYTHONPATH="$PWD/.deps:$PWD" python3 -m pytest tests/ -q
```

Includes a full end-to-end intelligence loop test:
observation → evidence → pattern → belief → opportunity → decision → experiment → learning.

---

## Philosophy

- No fake certainty
- No conflating estimates with actuals
- LLM is a reasoning component, not the database of truth
- Policy gates all consequential actions
- Progressive improvement through contact with reality

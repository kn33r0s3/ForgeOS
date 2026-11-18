# GATES INVENTORY — every way Hami reaches outside itself or changes real-world state

Generated from the real repo (code, not docs). Scanned 2026-11-18 ~12:00 UTC.
Scan evidence: /tmp/gates-inventory-raw2.txt (1,233 lines), /tmp/gates-inventory-raw3.txt (323 lines).

Conventions:
- **State** is the DEFAULT in code (what the flag defaults to). The live value in
  `backend/.env` was NOT read (values are never read). A default of `false`/empty
  means CLOSED unless the owner set it otherwise; that live value is UNKNOWN here.
- **Via gate?** means the path goes through the central decision service
  `execute_through_gate` (`backend/app/services/execution_engine.py:1149`).
  The gate covers 10 repo-local operations plus `SEND_EMAIL`, `SEND_SMS`, and
  `SEND_TELEGRAM`; each send operation handles one validated outbox delivery
  and independently verifies provider acceptance.
- **Via middleware?** means the path is covered by the global `api_key_middleware`
  (`backend/app/security.py:145`, wired in `backend/app/main.py`). It guards
  state-changing HTTP (POST/PUT/PATCH/DELETE) and private reads when a key is
  configured OR the runtime is deployed. Local dev with no key is open by design.

## 1. The two front doors (as built today)

| Front door | File:line | What it covers | Gap |
|---|---|---|---|
| Decision service `execute_through_gate` | `backend/app/services/execution_engine.py:1149` | 10 repo-local ops + 3 outbox send ops; HALT fail-closed; idempotency; refusal recorded; independent postcondition | No known send bypass remains. |
| API key middleware `api_key_middleware` | `backend/app/security.py:145` (wired in `backend/app/main.py`) | State-changing HTTP + private substrate/contact reads, when key configured or deployed | GET `/scheduled/cycle` has its own owner-key check in addition to `CRON_SECRET`; other GETs remain read-only by route contract. |
| Outbox + dispatcher | `backend/app/services/integration_outbox.py` (enqueue) + `backend/app/services/integration_dispatcher.py` (send) | SMTP/Twilio/Telegram delivery intent is queued first; each provider call runs inside a SEND operation | Telegram webhook and ASK paths enqueue through this funnel. |

## 2. Sending — SMTP (email)

| Sender | File:line | State (default) | Via gate? | Via outbox? |
|---|---|---|---|---|
| `send_owner_summary_notification` | `backend/app/api/forge_bot_owner_notification.py:35` | CLOSED (needs SMTP creds + `FORGE_BOT_LIVE` + `FORGE_BOT_RESPONSE_SEND_ENABLED`; creds default empty) | Yes — `SEND_EMAIL` | Yes (enqueue at :215, :346) |
| `send_owner_test_notification` | `backend/app/api/forge_bot_owner_notification.py:78` | CLOSED (same creds gate) | Yes — `SEND_EMAIL` | Yes |
| `send_daily_owner_summary_notification` | `backend/app/api/forge_bot_owner_notification.py:95` | CLOSED (same creds gate) | Yes — `SEND_EMAIL` | Yes |
| `retry_queued_owner_notifications` | `backend/app/api/forge_bot_owner_notification.py:290` | CLOSED (same creds gate) | Yes — `SEND_EMAIL` | Yes |

SMTP config: `backend/app/config.py:155-162` (`SMTP_HOST/PORT/USER/PASSWORD/FROM_EMAIL`, all default empty; `SMTP_USE_TLS` defaults true but is inert without creds).
Callers: `backend/app/api/forge_bot.py:411` (test send), `:914` (summary on lead); `backend/app/api/scheduled.py:423` (daily summary), `:911` (retry).

## 3. Sending — Telegram (owner only)

| Sender / call site | File:line | State (default) | Via gate? | Via outbox? |
|---|---|---|---|---|
| `send_owner_message` (the transport) | `backend/app/services/telegram_transport.py:12` | CLOSED (needs `HAMI_TELEGRAM_CONTROL_ENABLED=true` + token ≥30 chars + valid owner chat id) | No | N/A (it IS the transport) |
| Dispatcher call site | `backend/app/services/integration_dispatcher.py` | CLOSED (same) | Yes — `SEND_TELEGRAM` | Yes — the outbox consumer |
| API webhook reply | `backend/app/api/owner_control.py` | CLOSED (same) | Yes — queued and dispatched as `SEND_TELEGRAM` | Yes |
| Owner ASK creation/resend | `backend/app/services/owner_control.py` | CLOSED (same) | Yes — queued and dispatched as `SEND_TELEGRAM` | Yes |

Telegram config: `backend/app/config.py:148-153` (`HAMI_TELEGRAM_BOT_TOKEN`, `HAMI_TELEGRAM_WEBHOOK_SECRET`, `HAMI_TELEGRAM_OWNER_CHAT_ID`, `HAMI_TELEGRAM_OWNER_USER_ID` default empty; `HAMI_TELEGRAM_CONTROL_ENABLED` and `HAMI_TELEGRAM_OWNER_DIGEST_ENABLED` default `false`).
The Telegram channel itself is BUILT (transport + webhook + owner ask/answer routes exist). Whether the bot is actually connected (token set, webhook registered) is UNKNOWN — the values were not read.

## 4. Sending — Twilio SMS (owner digest only)

| Sender | File:line | State (default) | Via gate? | Via outbox? |
|---|---|---|---|---|
| `send_daily_owner_status_sms` | `backend/app/api/forge_bot_owner_notification.py:138` | CLOSED (needs Twilio creds + `HAMI_OWNER_SMS_DIGEST_ENABLED`; creds default empty) | Yes — `SEND_SMS` | Yes (enqueue at :215) |

Twilio config: `backend/app/config.py:135-144` (`TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER` default empty; `HAMI_OWNER_SMS_NUMBER` default empty; `HAMI_OWNER_SMS_DIGEST_ENABLED` default `false`).
Caller: `backend/app/api/scheduled.py:934` (daily SMS inside the cycle).

## 5. Intake (web form) — CLOSED by default

| Item | File:line | State (default) |
|---|---|---|
| `FORGE_BOT_INTAKE_ENABLED` | `backend/app/config.py:213-214` | `false` — CLOSED. POST `/forge-bot/leads` returns 503 when false (`backend/app/api/forge_bot.py:808`). |
| `FORGE_BOT_LIVE` | `backend/app/config.py:205` | `false` — CLOSED. Real lead intake requires `FORGE_BOT_LIVE=true` (`backend/app/api/forge_bot.py:843`). |
| Intake state machine | `backend/app/config.py:207-212` (comment) | INTAKE=false, LIVE=false → disabled. INTAKE=true, LIVE=false → test/synthetic only. Both true → real customer activity possible. |
| Intake page | `src/routes/forge-bot-intake.tsx:100,221` | Renders closed state when `intake_enabled` is false. |
| Owner readiness display | `src/routes/owner.tsx:1074,1773,1829,1899-1902` | Shows Intake ON/OFF and LIVE ON/OFF; warns to keep both closed until the checklist is approved. |

## 6. Flags — every gate flag (all default CLOSED)

| Flag | File:line | Default | What it opens |
|---|---|---|---|
| `FORGE_BOT_LIVE` | `backend/app/config.py:205` | `false` | Real external/customer-facing side effects. Owner decision only; code never enables it. |
| `FORGE_BOT_INTAKE_ENABLED` | `backend/app/config.py:213-214` | `false` | Web form accepts submissions. |
| `FORGE_BOT_RESPONSE_SEND_ENABLED` | `backend/app/config.py:228-229` | `false` | Customer-facing response sending. |
| `FORGEOS_PUBLIC_CHECKOUT_ENABLED` | `backend/app/config.py:130-132` | `false` | Public checkout (eSewa/Khalti). |
| `HAMI_TELEGRAM_CONTROL_ENABLED` | `backend/app/config.py:152` | `false` | Telegram owner control (sends + webhook replies). |
| `HAMI_TELEGRAM_OWNER_DIGEST_ENABLED` | `backend/app/config.py:153` | `false` | Telegram owner digest. |
| `HAMI_OWNER_SMS_DIGEST_ENABLED` | `backend/app/config.py:141-143` | `false` | Owner SMS digest (Twilio). |
| `FORGE_API_KEY` | `backend/app/config.py:195` | `""` (empty) | When set, deployed state-changing/private reads require `X-API-Key`. When empty, deployed runtimes fail closed (503). Local dev is open. |
| `HAMI_MAINTENANCE_MODE` | (referenced in code; default not verified in this scan) | UNKNOWN | Maintenance mode. Verify in `backend/app/config.py` before relying on it. |

No gate flag is open by default. Verified from `backend/app/config.py` (all `os.getenv(..., "false")` or `""`).

## 7. Publishing to public pages

Public pages render from the database and from static content. The claim rule
is enforced by the evidence gate (`src/lib/evidence.ts: verifyClaim`) and, for
the new proof ledger, by the ledger gate (`src/lib/ledger.ts: verifyLedgerClaim`).

| Surface | File | Claim rule |
|---|---|---|
| Discoveries / findings | `src/routes/` (discoveries), `src/lib/content.ts` | Evidence gate (`verifyClaim`) — a claim needs a class, sources, confidence, weakest link. |
| Unknowns | `src/routes/unknowns.tsx`, `src/lib/unknowns.ts` | Synced from `UNKNOWN_MAP.md` via `scripts/sync-unknowns-json.mjs` (never hand-edited). |
| Experiments | `src/routes/experiments.tsx`, `src/components/experiments/experiment-card.tsx` | Real log only; EXP-1 is `proposed` with an empty log. |
| Public proof ledger (new) | `src/lib/ledger.ts`, `src/routes/ledger.tsx` (to build) | Ledger gate — a claim renders only with state + evidence; ESTIMATED never as ACTUAL; contradicted claims shown. |
| Public offers | `src/routes/experiments.tsx` (PublicOffers) | Fetches `/api/opv4/offers/public`; only `public_copy` offers render, only after owner approval. |

No personal data on public pages: contact PII is key-gated (`PRIVATE_CONTACT_READ_PATH_PREFIXES`, `backend/app/security.py:39-50`), and the log filter masks phones/emails (`backend/app/main.py: PIIMaskFilter`).

## 8. Payment — eSewa / Khalti (no Stripe)

No Stripe code exists (the only "stripe" hits are CSS "pinstripe"). Payment is
Nepali eSewa + Khalti.

| Item | File:line | State (default) |
|---|---|---|
| `FORGEOS_PUBLIC_CHECKOUT_ENABLED` | `backend/app/config.py:130-132` | `false` — CLOSED. |
| Payments API | `backend/app/api/payments.py` | Checkout initiation is NOT allowlisted (only the two attempt-bound reconcile POSTs are, `backend/app/security.py:95-120`). |
| Nepal payments service | `backend/app/services/nepal_payments.py` | eSewa/Khalti merchant config from env (`ESEWA_MERCHANT_CODE`, `ESEWA_SECRET_KEY`, `KHALTI_SECRET_KEY`, etc., all default empty). |
| Checkout attempt storage | `src/lib/checkout-attempt-storage.ts` | Fail-closed; providers `"esewa" \| "khalti"`; refuses without a cryptographic source. |
| Public write allowlist (payments) | `backend/app/security.py:95-120` | Only `/payments/intent/{ref}/reconcile` and `/payments/products/{id}/checkout/reconcile` (attempt-bound). Checkout initiation is deliberately NOT allowlisted. |

## 9. Scheduled jobs

| Job | File:line | Trigger | What it does (outward) |
|---|---|---|---|
| Cycle | `backend/app/api/scheduled.py:340` (`GET /cycle`) | HTTP GET requires the `CRON_SECRET` bearer token and `X-API-Key` | Runs the daily cycle; email/SMS sends use the decision gate. The route checks the owner key because GET is not covered by write middleware. |
| Intelligence | `backend/app/api/scheduled.py:456` (`GET /intelligence`) | HTTP GET | Intelligence pipeline run (read/collect). |
| CI (GitHub Actions) | `.github/workflows/forgeos-ci.yml` | push to `main`, PR to `main` | backend-tests, evidence-triage-tests, frontend-tests, typecheck, lint, build, route-smoke, secret-scan (gitleaks), repository-guards, livekit-local-smoke. |
| Secret scan | `.github/workflows/secrets.yml` | push, PR, workflow_call | gitleaks. |
| Verify deploy | `.github/workflows/verify-deploy.yml` | push to `main`, workflow_dispatch | Deploy verification. |
| Hourly discovery push to main | **NOT FOUND in repo** | UNKNOWN | No hourly job, no `git push`, no scheduler found in `scripts/`, `.github/`, `scheduled.py`, or `cycle_scheduler.py`. See §11. |

## 10. API routes — 177 decorators (79 POST, 96 GET, 2 PATCH/PUT/DELETE)

Counted from the scan (section 9 of raw2). Every state-changing route is
covered by the GLOBAL `api_key_middleware` (not per-route wrappers) — so the
"gate wrapper" for a route IS the middleware, and the "allowlist entry" is
`PUBLIC_WRITE_PATHS` (`backend/app/security.py:25-42`).

Public write allowlist (each exact path has one sentence in
`backend/app/security.py`'s `PUBLIC_WRITE_REASONS` map):
- `/analyze`, `/api/analyze` — public analysis submission.
- `/hami/chat`, `/api/hami/chat` — Meet Hami chat (explicitly allowed through the key gate; commit 43df3419 "fix: allow Meet Hami chat through API key gate").
- `/public/booking-requests`, `/api/public/booking-requests` — public booking request.
- `/public/domain`, `/api/public/domain` (+ `/public/domain/*`) — public domain submission.
- `/forge-bot/leads`, `/forge-bot/leads/opt-out`, `/forge-bot/leads/delete` (+ `/api/` variants) — consent-scoped lead intake + opt-out/delete (privacy: a person must be able to opt out without a key).
- `/owner-control/telegram/webhook`, `/api/owner-control/telegram/webhook` — Telegram must be able to POST the webhook without a key (it authenticates by webhook secret instead).
- `/signals/public-request`, `/api/signals/public-request` — public signal/request submission.
- Plus the two attempt-bound payment reconcile POSTs (see §8).

All other state-changing routes require `X-API-Key` when a key is configured
or the runtime is deployed, and fail closed (503) when deployed without a key.

## 11. UNKNOWN — things this scan could not establish from code

- **Hourly discovery push to main**: no hourly job or `git push` exists in the
  repo (searched `scripts/`, `.github/`, `scheduled.py`, `cycle_scheduler.py`).
  It may be an external cron/launchd on the Mac, a ChatGPT scheduled task, or
  a job that no longer exists. Do NOT assume it exists or that it conflicts
  with branch protection until it is found. If it is a Mac launchd/cron, its
  definition lives outside this repo.
- **Branch protection on `main`**: GitHub API returns HTTP 401 without auth
  for `/repos/kn33r0s3/ForgeOS/branches/main/protection`. Cannot determine
  whether branch protection (or required status checks) is on. UNKNOWN.
- **Live flag values**: `backend/.env` exists (137 bytes) but its values were
  NOT read. Whether any flag is actually open in production is UNKNOWN.
- **Telegram bot connected?**: the transport + webhook exist, but whether the
  bot token is set and the webhook is registered is UNKNOWN (values not read).
- **`HAMI_MAINTENANCE_MODE` default**: referenced in code; its default was not
  verified in this scan. UNKNOWN.
- **Who calls `GET /scheduled/cycle`**: no in-repo caller found. If an external
  cron calls it, that cron is outside this repo. UNKNOWN.

## 12. Bypasses found and disposition

1. **Telegram webhook reply** — fixed: `backend/app/api/owner_control.py` enqueues the reply; the dispatcher invokes the transport only inside `SEND_TELEGRAM`.
2. **Telegram owner ASK creation/resend** — fixed: both paths enqueue with stable per-ASK idempotency keys; provider response IDs are read from the outbox.
3. **GET `/scheduled/cycle` owner authorization** — fixed: retains the `CRON_SECRET` bearer check and additionally calls `require_owner_api_key`; the HTTP method and path are unchanged.
4. **Decision service send operations** — fixed: `SEND_EMAIL`, `SEND_SMS`, and `SEND_TELEGRAM` use dispatcher-only scopes, HALT/refusal/idempotency checks, and independent outbox postconditions.
5. **Public write reasons** — fixed: `PUBLIC_WRITE_REASONS` describes every existing `PUBLIC_WRITE_PATHS` entry; the path set is unchanged.

## 13. What is already correct (do not break)

- All gate flags default CLOSED (`false`/empty). Verified in `backend/app/config.py`.
- `api_key_middleware` fails closed on deployed runtimes without a key (503).
- The outbox/dispatcher funnel is the only sender path; SMTP, Twilio, and Telegram provider calls run through the decision service.
- Senders fail closed when credentials are missing (SMTP/Twilio/Telegram all check creds first).
- CI already runs tests + secret scan on push/PR to main (`.github/workflows/forgeos-ci.yml`, `secrets.yml`).
- PII is masked in logs (`PIIMaskFilter`) and contact reads are key-gated.
- No Stripe code; payment is eSewa/Khalti, checkout closed by default.

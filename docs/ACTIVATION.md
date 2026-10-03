# Forge Bot readiness, activation, and daily check

This document is a runbook, not authorization. Intake and `FORGE_BOT_LIVE`
must remain closed until all readiness checks pass and the owner writes the
exact activation phrase below. No action in this document has been run.

## Readiness check

Run this checklist whenever the owner asks for a readiness check. Record each
row as **PASS** or **FAIL**, with the date and evidence. A missing, stale, or
unverified item is FAIL; do not infer a pass.

| Check | PASS evidence |
| --- | --- |
| Tests green | Current CI/local evidence for backend SQLite and PostgreSQL tests, `npm test`, typecheck, lint, and build. |
| Deployed commit equals `origin/main` | Vercel deployment commit SHA exactly matches the current `origin/main` SHA. |
| Rate limits active | Deployed code has durable visitor-HMAC limits and request-size caps; database is PostgreSQL; regression tests pass. |
| Maintenance heartbeat under 26 hours | Owner readiness endpoint reports `last_maintenance_age_seconds < 93600`. |
| Test email sent and received within 7 days | Owner readiness endpoint has a test result/time in the last 7 days, and the owner confirms actual mailbox receipt. SMTP acceptance alone is not receipt. |
| Backup drill within 7 days | Dated dump-and-restore evidence from a throwaway database, with matching table list and row counts. |
| Privacy text approved in owner chat | The owner explicitly approves the exact currently deployed privacy text in chat. |
| Health is OK | Read-only `/api/health` response reports `status: "ok"` and `ready: true`. |
| Intake still closed | Read-only `/api/forge-bot/config` on both production domains reports `intake_enabled: false`; the readiness endpoint reports both flags off. |

The owner console's readiness endpoint reports only operational booleans,
timestamps, a deployed commit identifier, and aggregate counts. It does not
prove external receipt, owner approval, or a real outcome.

## Activate

Activation is allowed only after the owner writes exactly:

`ACTIVATE FORGE BOT LIVE`

Do not interpret "go", "ok", "yes", or any other wording as authorization.
First complete the readiness checklist above; if any item is FAIL, stop with
both production flags unchanged and closed.

With the correct Vercel project selected, update the two Production environment
values through the Vercel CLI. If a value already exists, remove that named
Production value first, then add it again and enter the literal `true` at the
CLI prompt:

1. Set `FORGE_BOT_LIVE=true` in Production.
2. Set `FORGE_BOT_INTAKE_ENABLED=true` in Production.
3. Run `vercel deploy --prod` and wait until that deployment reports READY.
4. Make read-only GET requests to
   `https://haminp.vercel.app/api/forge-bot/config` and
   `https://forge-os-ebon.vercel.app/api/forge-bot/config`. Both must return
   HTTP 200 and `intake_enabled: true`. Record the deployment URL and commit.
5. If either domain is not READY or does not report `true`, do not treat
   activation as successful. Follow the close procedure below, redeploy, and
   verify both domains report `false`.

The CLI commands for adding the values are:

```sh
vercel env rm FORGE_BOT_LIVE production
vercel env add FORGE_BOT_LIVE production
# Enter: true
vercel env rm FORGE_BOT_INTAKE_ENABLED production
vercel env add FORGE_BOT_INTAKE_ENABLED production
# Enter: true
vercel deploy --prod
```

Skip a corresponding `env rm` only when Vercel confirms that no value exists.
Do not pipe or print any unrelated environment value; these two entries are
the boolean literal `true`, not credentials.

Do not send customer messages or create synthetic `REAL` inquiries as part of
activation. Verify the deployed switch with GET only. The intake path can be
exercised beforehand on a local PostgreSQL/mail-sink stack using reserved test
contacts and `TEST` classification; erase that test inquiry afterward. On
activation day, do not submit a fabricated production inquiry. A production
`REAL` record must originate from a real person who provides consent; otherwise
wait for an actual stranger to submit it.

## Close

Close only after the owner writes exactly:

`CLOSE FORGE BOT`

Set both `FORGE_BOT_INTAKE_ENABLED=false` and `FORGE_BOT_LIVE=false` in
Production through the Vercel CLI, redeploy with `vercel deploy --prod`, wait
for READY, then verify by GET that `/api/forge-bot/config` reports
`intake_enabled: false` on both production domains. The one-step safety
response to any failed activation check is this close-and-redeploy procedure;
do not leave one flag enabled while investigating.

For the close procedure, remove any existing Production values, add each name
again, and enter the literal `false` at each prompt:

```sh
vercel env rm FORGE_BOT_INTAKE_ENABLED production
vercel env add FORGE_BOT_INTAKE_ENABLED production
# Enter: false
vercel env rm FORGE_BOT_LIVE production
vercel env add FORGE_BOT_LIVE production
# Enter: false
vercel deploy --prod
```

## Activation-day path verification without misleading evidence

1. Before production activation, exercise consent, persistence, owner notice,
   lifecycle, and erase on the local PostgreSQL stack with a reserved test
   address (`@example.test`) and reserved test phone (`202-555-01xx`).
2. Confirm the resulting row and events remain `TEST`; confirm no test row is
   counted as REAL; erase the test record and confirm only the non-contact
   erasure event remains.
3. After activation, use read-only GETs to verify configuration, health, and
   deployed commit. Do not POST a made-up inquiry to production.
4. When a real stranger independently submits with consent, verify the owner
   notification and record subsequent reply, booking, and completion only
   against actual evidence. Keep the real lead's contact data out of audit
   notes and reports.

## DAILY CHECK

When the owner writes `DAILY CHECK`, report:

- Latest maintenance heartbeat timestamp and age from the owner readiness
  endpoint.
- Age of the oldest unsent or failed owner-email delivery, or that none is
  present.
- New lead count in the last 24 hours and current stage/evidence-class counts;
  never include contact fields or lead-supplied text.
- Error counts since the previous day from the deployment's function/runtime
  logs, summarized by error class and route only. Do not copy request bodies,
  addresses, headers, or secret values into the report.
- Read-only health status and readiness.

If logs cannot provide a defensible count, mark it UNKNOWN and state which
read-only log view or permission is missing. A quiet log window is not proof
that a real customer path worked.

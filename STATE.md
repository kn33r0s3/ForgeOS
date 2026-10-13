# Hami Operating State

**Snapshot date:** 2026-10-14 (Asia/Kathmandu). This file records verified facts and known unknowns; it is not a claim that unattended operation is already live.

## Current truth

- **Mission:** one Hami system for discovering real needs, capabilities, relationships and outcomes, then creating authorized action and measurable value. Preserve the six substrate primitives: ENTITY, RELATION, EVENT, EVIDENCE, CAPABILITY, ACTION. Do not build parallel semantic tables or a seller-only product identity.
- **Repository:** kn33r0s3/ForgeOS, canonical branch main. Latest observed base before this charter sync: 6f080dad3cfea3db2c55e4a2317f9d0081d0ff7c. Refresh main every run; never assume this SHA is still current.
- **Deployment:** Vercel's prior read for base dba7d5b064de72dc505bed3603254b3e2acdeb96 reported READY at a generated hostname; current main is 6f080dad3cfea3db2c55e4a2317f9d0081d0ff7c. Current deployed SHA and assignment to haminp.vercel.app are UNVERIFIED. A READY deployment does not prove runtime readiness.
- **CI:** on parent base dba7d5b064de72dc505bed3603254b3e2acdeb96, frontend tests, typecheck, evidence triage, route smoke, secret scan, lint, build and repository guards passed while backend tests were running. Current main SHA 6f080dad3cfea3db2c55e4a2317f9d0081d0ff7c has a new run in progress. Full exact-head required checks are NOT YET VERIFIED GREEN.
- **Production health:** fresh health/config/alias reads were not verified through the current connected path; prior Vercel access to protected deployment information was denied. Do not claim flags, database durability, cron execution, email/SMS delivery or customer sending are healthy/active without new read evidence.
- **Autonomy:** production ACTIVE_STAGE remains 1 in the decision-rights registry. Do not advance it by editing a number or by making tests permissive. Any advancement requires evidence against the stage gates and explicit owner authorization.
- **Inbound and publishing:** the intended posture is inbound-first and no cold mass outreach. The repo does not yet have a verified official social-publishing connection in this snapshot. The generic provider_publish, outreach, general SMS/email and ForgeBot customer-response actions are currently owner-only or separately gated. Never infer permission to send from the presence of an adapter.
- **Intake and customer sends:** configuration/code defaults are closed unless specifically enabled. A fresh live flag read was not verified in this run; do not claim the deployed flags are confirmed OFF, and do not enable them as a workaround.
- **Owner digest:** commit 1107abd adds a daily owner-only SMS digest behind HAMI_OWNER_SMS_DIGEST_ENABLED, with exact-recipient checks and a PostgreSQL durability requirement. Provider credentials, the flag, successful delivery, and handset receipt have not been verified here. Do not claim SMS is active. Any spend or credential/permission changes remain gated.
- **Reality and money:** the latest recorded project snapshot is pre-revenue with zero verified commercial ledger entries and no verified REAL payment. No real customer, lead, conversation, recovered sale, or revenue is claimed by this run. Confirm every value claim against its own evidence.
- **Owner time:** the operating target is zero routine manual posting/management by the owner. One-time account/OAuth setup, owner-only permission decisions, legal signatures, financial custody, spend approvals, and any genuinely human-only conversation must be handled as explicit dependencies—not silently turned into recurring manual work.

## Truth labels

REAL requires traceable evidence. REQUESTED is not BOOKED. ESTIMATED is not ACTUAL. TEST/MOCK/HYPOTHESIS must not be represented as REAL. Owner-reported evidence must remain labeled as owner-reported unless independently verified.

## Required per-run behavior

Read docs/BRAIN.md, this file, QUEUE.md, AGENTS.md, HANDOFF.md, and the relevant existing subsystem docs. Refresh main, production deployment SHA, exact-commit CI, activation flags, cron execution evidence and provider readiness. Take the highest-ranked unblocked QUEUE item. Verify changes with tests/readbacks, then append to LOG.md and update this snapshot. Never report a deployment, message, revenue, or autonomous run that was not observed.

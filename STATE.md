# Hami Operating State

**Snapshot date:** 2026-10-14 (Asia/Kathmandu). This file records verified facts and known unknowns; it is not a claim that unattended operation is already live.

## Current truth

- **Mission:** one Hami system for discovering real needs, capabilities, relationships and outcomes, then creating authorized action and measurable value. Preserve the six substrate primitives: ENTITY, RELATION, EVENT, EVIDENCE, CAPABILITY, ACTION. Do not build parallel semantic tables or a seller-only product identity.
- **Repository:** kn33r0s3/ForgeOS, canonical branch main. Product-code baseline observed at commit 1107abd3b3f3f0d4139f59bdf93c9b3d63febe7a. Always refresh the branch ref at the start of the next run.
- **Deployment:** Vercel reports a READY production deployment from commit 1107abd3b3f3f0d4139f59bdf93c9b3d63febe7a and lists haminp.vercel.app as a project domain. A READY deployment is not proof that the live API, database, cron, or messaging providers are healthy.
- **CI:** at snapshot time the 1107abd backend-tests job was still running. Its parent 42beaf0 CI run had 16 failed backend tests (1,126 passed, 2 skipped); therefore the current backend gate must be treated as NOT GREEN until the exact latest-main run completes successfully. Non-backend checks observed on 1107abd were successful at that time.
- **Production health:** a fresh health/config read was not available through the current connected read path. An earlier HANDOFF snapshot reported differing health between aliases; that report is historical, not proof of current failure or current health. Re-verify before any activation.
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

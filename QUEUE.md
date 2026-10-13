# Hami Execution Queue

Ranked by nearest proof gate and reliability blockers. This file is intentionally compact; docs/CAPABILITY_QUEUE.md remains the detailed capability ledger. Re-rank after every run based on new evidence.

## P0 — Make main verifiably safe

1. **Get backend CI green on the exact current main SHA.** On parent base dba7d5b064de72dc505bed3603254b3e2acdeb96, frontend tests, typecheck, evidence triage, route smoke, secret scan, lint, build and repository guards passed while backend tests were running. Main then advanced to 6f080dad3cfea3db2c55e4a2317f9d0081d0ff7c; refresh that run and fix proven failures without weakening ACTIVE_STAGE=1, owner-only first contact, consent, source continuity, payment truth or dispatch gates. Stop when all required checks pass on one exact SHA or each remaining failure has an evidence-backed blocker.

2. **Reconcile main, deployment and runtime truth.** The prior deployment read reported READY for parent base dba7d5b064de72dc505bed3603254b3e2acdeb96 at a generated hostname, but current main is 6f080dad3cfea3db2c55e4a2317f9d0081d0ff7c. Current deployed SHA, custom-domain assignment and live health remain unverified. Re-check haminp.vercel.app, health/database readiness, activation flags, actual scheduled invocation and provider status through an authorized path. Do not open intake or customer sending while tests or readiness are unknown.

## P1 — Remove routine owner work by building the real ForgeBot loop

3. **Make daily orchestration durable.** Reuse the existing scheduled intelligence/cycle endpoints, worker and outbox seams; verify a real scheduled invocation and persisted result, not merely that a cron declaration exists. Each run reads BRAIN/STATE/QUEUE, takes the top unblocked action, logs evidence, and updates STATE/LOG. Failures must be isolated and visible.
4. **Build the bilingual content loop without narrowing Hami's mission.** Research the actual discovery log and approved public sources; generate Nepali and English drafts that test competing real-need hypotheses, not just seller-reply messaging. Store drafts and provenance in existing substrate/projection seams rather than adding a parallel semantic model. No fabricated success claims.
5. **Implement governed hands-off publishing through official channel APIs.** Reuse an existing connected channel if one is actually verified; otherwise identify the minimum one-time account/OAuth dependency. Align a narrowly scoped pre-approved-content action with the charter's bot-then-notify-owner right, with explicit per-content-type and destination allowlists, idempotency, audit events, takedown/kill-switch handling, and hard owner-only gates for new message types, channels, audiences, claims, spend or permissions. Do not reinterpret generic provider_publish/outreach permission or publish without an ALLOWED authorization and verified channel credentials.
6. **Close the consented inbound loop.** Capture inbound consent and opt-out state, answer only through approved templates and the verified channel, create traceable seller/entity/event/evidence records, and onboard consenting participants. Intake and customer sends stay closed until all activation criteria are evidenced. No cold or mass outbound.
7. **Finish the owner control plane.** Verify the exact-recipient, confirmation-code ASK/reply path, STOP kill switch, bounded owner digest, spend guard and delivery/audit records. The daily SMS digest added in 1107abd is explicitly disabled by default and needs durable PostgreSQL plus configured provider credentials. Never enable cost-bearing delivery without the required owner approval; report provider acceptance separately from handset delivery.
8. **Run the separate QA adversary and recovery drills.** Test blocked dispatch cannot send, stale/revoked authorization fails closed, duplicate delivery cannot repeat after ambiguous outcome, owner commands require the verified number and confirmation code, and backup/restore works. Do not let the implementation agent mark its own checks sufficient.

## P2 — Advance the nearest commercial proof gate

9. **Measure the first REAL recovered sale.** The Phase 1 kill criterion is ten genuine seller conversations with no recovered sale. Do not fabricate conversations to satisfy it. Track actual owner minutes, consent, reply time, recovered sale, costs and independently supported REAL rupees. If the thesis dies, record it and pivot to the evidence from discovery.
10. **Defer expansion.** No new marketplace/resource hub or unrelated platform expansion until the current phase gate is passed. Keep the broad economic-intelligence mission; narrow only the next experiment, never Hami's identity.

## Global stop conditions

No non-consensual contact, no spend without approval, no legal/company/tax commitment without the owner, no invented results, no permission self-escalation, no casual deletion, no public activation while tests or live readiness are unknown. When blocked, record the legitimate workaround and keep moving on unblocked internal work.

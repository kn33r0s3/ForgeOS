# Hami Execution Queue

Ranked by nearest proof gate and reliability blockers. This file is intentionally compact; docs/CAPABILITY_QUEUE.md remains the detailed capability ledger. Re-rank after every run based on new evidence.

## P0 — Make main verifiably safe

1. **Get full CI green on one exact current main SHA.** The verifier for `b47f7ba` failed because root frontend tests had 2 failures out of 254; its deployment SHA matched and the protected owner-cycle read passed. Later commits updated copy guards and added provider/privacy checks. Current main at the start of this refresh is `751d5851f9c4142627d048a129c751376b8ade0e`, with its ForgeOS CI pending, verifier pending, and secrets scan queued. Fix genuine failures without weakening consent, authorization, provenance, payment truth or provider/data privacy.

2. **Bound deployment verification and reconcile live runtime truth.** `.github/workflows/verify-deploy.yml` has no job-level timeout and unbounded page/readiness/verification requests. Add a 10-minute job limit and 10-second connection / 30-second request limits. The last specific Vercel metadata read was READY for source `1e6875d`, while main has moved past that SHA; protected runtime health/flag/scheduler/provider reads remain unverified. Keep intake, publishing and customer sends closed until the new deployed source and runtime state are observed.

## P1 — Remove routine owner work by building the real ForgeBot loop

3. **Make daily orchestration durable.** Reuse the existing scheduled intelligence/cycle endpoints, worker and outbox seams; verify a real scheduled invocation and persisted result, not merely that a cron declaration exists. Each run reads BRAIN/STATE/QUEUE, takes the top unblocked action, logs evidence, and updates STATE/LOG. Failures must be isolated and visible.
4. **Build the bilingual content loop without narrowing Hami's mission.** Research the actual discovery log and approved public sources; generate Nepali and English drafts that test competing real-need hypotheses, not just seller-reply messaging. Store drafts and provenance in existing substrate/projection seams rather than adding a parallel semantic model. No fabricated success claims.
5. **Implement governed hands-off publishing through official channel APIs.** Reuse an existing connected channel if one is actually verified; otherwise identify the minimum one-time account/OAuth dependency. Align a narrowly scoped pre-approved-content action with the charter's bot-then-notify-owner right, with explicit per-content-type and destination allowlists, idempotency, audit events, takedown/kill-switch handling, and hard owner-only gates for new message types, channels, audiences, claims, spend or permissions. Do not reinterpret generic provider_publish/outreach permission or publish without an ALLOWED authorization and verified channel credentials.
6. **Close the consented inbound loop.** Capture inbound consent and opt-out state, answer only through approved templates and the verified channel, create traceable seller/entity/event/evidence records, and onboard consenting participants. Intake and customer sends stay closed until all activation criteria are evidenced. No cold or mass outbound.
7. **Finish the owner control plane.** Verify the exact-recipient, confirmation-code ASK/reply path, HALT owner kill switch plus recipient-level STOP opt-out, bounded owner digest, spend guard and delivery/audit records. The daily SMS digest added in 1107abd is explicitly disabled by default and needs durable PostgreSQL plus configured provider credentials. Never enable cost-bearing delivery without the required owner approval; report provider acceptance separately from handset delivery.
8. **Run the separate QA adversary and recovery drills.** Test blocked dispatch cannot send, stale/revoked authorization fails closed, duplicate delivery cannot repeat after ambiguous outcome, owner commands require the verified number and confirmation code, and backup/restore works. Do not let the implementation agent mark its own checks sufficient.

## P2 — Advance the nearest commercial proof gate

9. **Measure the first REAL recovered sale.** The Phase 1 kill criterion is ten genuine seller conversations with no recovered sale. Do not fabricate conversations to satisfy it. Track actual owner minutes, consent, reply time, recovered sale, costs and independently supported REAL rupees. If the thesis dies, record it and pivot to the evidence from discovery.
10. **Defer expansion.** No new marketplace/resource hub or unrelated platform expansion until the current phase gate is passed. Keep the broad economic-intelligence mission; narrow only the next experiment, never Hami's identity.

## Global stop conditions

No non-consensual contact, no spend without approval, no legal/company/tax commitment without the owner, no invented results, no permission self-escalation, no casual deletion, no public activation while tests or live readiness are unknown. When blocked, record the legitimate workaround and keep moving on unblocked internal work. Do not stop merely because a verification gate is blocked; continue source audits, non-external fixes, regression coverage and queue maintenance without claiming runtime success.
